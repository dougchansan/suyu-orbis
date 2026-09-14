# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from import_modules import import_modules, inspect_exports, verify_manifest, cmake_path
from doctor import inspect

# Hand-authored exporter-shaped fixture. This is NOT output of Suyu's emitter;
# test_upstream.py is the separate real-emitter integration test.
HEADER = r"""
#ifndef FIXTURE_RUNTIME_H
#define FIXTURE_RUNTIME_H
#include <stdint.h>
#include <stddef.h>
typedef struct RecompHostMem {
 void* user;
 uint64_t (*load)(void*,uint64_t,uint32_t);
 void (*store)(void*,uint64_t,uint32_t,uint64_t);
 uint64_t (*excl_load)(void*,uint64_t,uint32_t);
 uint32_t (*excl_store)(void*,uint64_t,uint32_t,uint64_t);
 void (*clear_excl)(void*);
 uint64_t (*read_cntpct)(void*);
 void (*excl_load_pair)(void*,uint64_t,uint32_t,uint64_t*,uint64_t*);
 uint32_t (*excl_store_pair)(void*,uint64_t,uint32_t,uint64_t,uint64_t);
 const void* page_entries;
 uint64_t page_entry_stride,page_bits,pointer_mask,address_space_max;
} RecompHostMem;
typedef struct GuestContext {
 uint64_t x[32],pc; uint8_t n,z,c,v;
 uint8_t* mem; uint64_t mem_size,mem_base_vaddr; int halted;
 uint64_t pending_svc,vreg[32][2],tpidr_el0;
 const RecompHostMem* host_mem;
 uint64_t tpidrro_el0,fpcr,fpsr; int chain_budget;
} GuestContext;
typedef void (*BlockFn)(GuestContext*);
#endif
"""
EXPORT = r"""
#include "recomp_runtime.h"
static uint64_t base;
void recomp_build_index(void) {}
int _recomp_index_view(void) { return 0; }
int recomp_image_index(void) { return _recomp_index_view(); }
static void step(GuestContext* c) { c->x[0] += 21; c->pc=c->x[30]; }
BlockFn recomp_image_lookup(uint64_t pc) { return pc==base ? step : NULL; }
void recomp_image_set_base(uint64_t value) { base=value; recomp_build_index(); }
uint64_t recomp_image_entry(void) { return 0; }
"""

def make_exports(root: Path) -> Path:
    for name in ['rtld','main']:
        d=root/name; (d/'src').mkdir(parents=True); (d/'data').mkdir()
        (d/'recomp_runtime.h').write_text(HEADER)
        (d/'recomp_runtime.c').write_text('void fixture_runtime(void) {}\n')
        (d/'recomp_export.c').write_text(EXPORT)
        (d/'src'/f'unit_{name}.c').write_text(f'void fixture_unit_{name}(void) {{}}\n')
        (d/'data/text.bin').write_bytes(bytes(8))
        (d/'CMakeLists.txt').write_text(f'''
if(NOT RECOMP_STATIC_ONLY)
  message(FATAL_ERROR "Must use static-only imports")
endif()
if(NOT TARGET recomp_runtime_shared)
  add_library(recomp_runtime_shared STATIC recomp_runtime.c)
  target_compile_definitions(recomp_runtime_shared PRIVATE RECOMP_STATIC_HOST=1)
endif()
add_library(recomp_static_{name} STATIC recomp_export.c src/unit_{name}.c)
target_include_directories(recomp_static_{name} PUBLIC ${{CMAKE_CURRENT_SOURCE_DIR}})
target_compile_definitions(recomp_static_{name} PRIVATE
 recomp_image_lookup=recomp_image_lookup_{name}
 recomp_image_set_base=recomp_image_set_base_{name}
 recomp_image_entry=recomp_image_entry_{name})
''')
    return root

class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='suyu orbis ')
        self.root=Path(self.tmp.name)
        self.exefs=make_exports(self.root/'exefs')
    def tearDown(self): self.tmp.cleanup()
    def test_order_and_all_new_symbol_renames(self):
        out=self.root/'bundle'; result=import_modules(self.exefs,out)
        self.assertEqual([m['name'] for m in result['modules']], ['rtld','main'])
        cm=(out/'CMakeLists.txt').read_text()
        for symbol in ['recomp_build_index','_recomp_index_view','recomp_image_index']:
            for name in ['rtld','main']: self.assertIn(f'{symbol}={symbol}_{name}',cm)
        self.assertFalse((out/'data').exists())
        verify_manifest(out/'manifest.json')
    def test_mixed_runtime_rejected(self):
        (self.exefs/'main/recomp_runtime.h').write_text(HEADER+'\n')
        with self.assertRaisesRegex(ValueError,'mixed runtime'): inspect_exports(self.exefs)
    def test_empty_and_unaligned_text_rejected(self):
        for data in [b'',b'123']:
            (self.exefs/'main/data/text.bin').write_bytes(data)
            with self.assertRaisesRegex(ValueError,'text size'): inspect_exports(self.exefs)
    def test_incomplete_export_rejected(self):
        (self.exefs/'main/recomp_export.c').unlink()
        with self.assertRaisesRegex(ValueError,'Missing'): inspect_exports(self.exefs)
    def test_missing_main_rejected(self):
        shutil.rmtree(self.exefs/'main')
        with self.assertRaisesRegex(ValueError,'rtld and main'): inspect_exports(self.exefs)
    def test_stale_sources_rejected(self):
        out=self.root/'bundle'; import_modules(self.exefs,out)
        (self.exefs/'main/recomp_export.c').write_text(EXPORT+'\n')
        with self.assertRaisesRegex(ValueError,'changed'): verify_manifest(out/'manifest.json')
    def test_stale_text_rejected(self):
        out=self.root/'bundle'; import_modules(self.exefs,out)
        (self.exefs/'main/data/text.bin').write_bytes(b'12345678')
        with self.assertRaisesRegex(ValueError,'text changed'): verify_manifest(out/'manifest.json')
    def test_added_source_rejected(self):
        out=self.root/'bundle'; import_modules(self.exefs,out)
        (self.exefs/'main/src/extra.c').write_text('int extra;')
        with self.assertRaisesRegex(ValueError,'source set changed'): verify_manifest(out/'manifest.json')
    def test_refuses_overwriting_outputs(self):
        out=self.root/'bundle'; import_modules(self.exefs,out)
        with self.assertRaisesRegex(ValueError,'empty'): import_modules(self.exefs,out)
    def test_does_not_write_inside_exports(self):
        with self.assertRaisesRegex(ValueError,'OUTSIDE'):
            import_modules(self.exefs,self.exefs/'bundle')
    def test_cmake_path_injection_rejected(self):
        with self.assertRaises(ValueError): cmake_path(Path('/tmp/a;message(bad)'))
    @unittest.skipUnless(shutil.which('cmake') and shutil.which('ninja'), 'CMake/Ninja required')
    def test_two_modules_really_link_and_dispatch(self):
        out=self.root/'bundle'; import_modules(self.exefs,out)
        with (out/'CMakeLists.txt').open('a') as f:
            f.write('\nadd_executable(bundle-link-test bundle_test.c)\n'
                    'target_link_libraries(bundle-link-test PRIVATE so_module_bundle)\n')
        (out/'bundle_test.c').write_text(r'''
#include "recomp_runtime.h"
#include "suyu_orbis/bundle.h"
int main(void) {
 GuestContext c={0}; SoBlockFn fn=0;
 if(so_bundle_init()!=SO_OK || so_bundle_bind(0,0x1000)!=SO_OK ||
    so_bundle_bind(1,0x2000)!=SO_OK || so_bundle_seal()!=SO_OK) return 1;
 for(size_t i=0;i<2;i++) {
  if(so_bundle_entry(i,&c.pc)!=SO_OK || so_bundle_lookup(c.pc,&fn)!=SO_OK) return 2;
  fn(&c);
 }
 return c.x[0]==42 ? 0 : 3;
}
''')
        build=self.root/'build'
        commands=[['cmake','-S',str(ROOT),'-B',str(build),'-G','Ninja',
                   '-DSO_BUILD_TESTS=OFF',f'-DSO_MODULE_BUNDLE={out}'],
                  ['cmake','--build',str(build),'--target','bundle-link-test']]
        for command in commands:
            result=subprocess.run(command,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        executable=build/'generated-bundle'/'bundle-link-test'
        result=subprocess.run([str(executable)],text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

class DoctorTests(unittest.TestCase):
    def test_missing_sdk_fails(self):
        result=inspect(True,'/a/nonexistent/sdk')
        self.assertFalse(result['ready'])
        self.assertIn('lib/crt1.o',result['missing'])

if __name__=='__main__': unittest.main()
