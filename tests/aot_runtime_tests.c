// SPDX-License-Identifier: GPL-2.0-or-later
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "recomp_runtime.h"
#include "suyu_orbis/abi_contract.h"
#include "suyu_orbis/aot.h"
#include "suyu_orbis/bundle.h"
#define CHECK(x) do { ++checks; if (!(x)) { fprintf(stderr,"AOT selftest line %d: %s\n",__LINE__,#x); return 1; } } while (0)
static SoBlockFn lookup(uint64_t pc) {
    SoBlockFn block = NULL;
    return so_bundle_lookup(pc, &block) == SO_OK ? block : NULL;
}
static uint64_t test_counter(void* raw) { return ++*(uint64_t*)raw; }
static SoAotResult until_event(SoAotMachine* m) {
    for (unsigned i=0;i<100;++i) {
        SoAotResult result=so_aot_run(m,100000);
        if (result!=SO_AOT_BUDGET) return result;
    }
    return SO_AOT_BUDGET;
}
int so_aot_selftest(void) {
    unsigned checks=0;
    const uint64_t rtld=UINT64_C(0x100000000), main=UINT64_C(0x200000000);
    const uint64_t buffer_va=UINT64_C(0x400000000);
    const unsigned width=320,height=256;
    uint32_t* pixels=calloc(width*height,sizeof(*pixels));
    CHECK(pixels);
    CHECK(so_bundle_count()==2);
    CHECK(so_bundle_init()==SO_OK && so_bundle_bind(0,rtld)==SO_OK &&
          so_bundle_bind(1,main)==SO_OK && so_bundle_seal()==SO_OK);
    CHECK(so_aot_create(NULL,NULL,NULL)==NULL);
    uint64_t ticks=100;
    SoAotMachine* m=so_aot_create(lookup,test_counter,&ticks);
    CHECK(m);
    CHECK(so_aot_set_pc(m,rtld) && so_aot_set_reg(m,16,main));
    CHECK(!so_aot_set_reg(m,32,0));
    GuestContext* c=so_aot_context(m);
    c->vreg[31][1]=UINT64_C(0xfedcba9876543210);
    c->tpidr_el0=0x123400; c->tpidrro_el0=0x567800;
    c->fpcr=0x400000; c->fpsr=0x10;
    CHECK(c->host_mem->read_cntpct(c->host_mem->user)==101);
    CHECK(so_memory_map(so_aot_memory(m),buffer_va,pixels,width*height*4,3));
    CHECK(so_aot_run(m,1)==SO_AOT_BUDGET);
    CHECK(so_aot_pc(m)==main && so_aot_get_reg(m,0)==42);
    for (unsigned frame=0;frame<4;++frame) {
        CHECK(until_event(m)==SO_AOT_SVC && so_aot_pending_svc(m)==0xf000);
        CHECK(so_aot_get_reg(m,0)==frame);
        const SoAotStats before=so_aot_stats(m);
        CHECK(so_aot_run(m,10)==SO_AOT_SVC && so_aot_stats(m).dispatches==before.dispatches);
        CHECK(!so_aot_resume(m,0xf001));
        CHECK(!so_aot_set_pc(m,main));
        CHECK(so_aot_set_reg(m,0,buffer_va) && so_aot_set_reg(m,1,width) && so_aot_set_reg(m,2,height));
        CHECK(so_aot_resume(m,0xf000));
        CHECK(until_event(m)==SO_AOT_SVC && so_aot_pending_svc(m)==0xf001);
        CHECK(so_aot_get_reg(m,0)==frame);
        CHECK(so_aot_memory(m)->stores==(uint64_t)(frame+1)*width*height);
        for (unsigned y=0;y<height;++y) for (unsigned x=0;x<width;++x) {
            uint32_t expected=0xff000000u | ((((x>>7)^frame)&1)*255u<<16) |
                (((x>>8)&1)*255u<<8) | (((y>>7)&1)*255u);
            if (pixels[y*width+x]!=expected) {
                fprintf(stderr,"AOT pixel mismatch phase=%u x=%u y=%u actual=%08x expected=%08x\n",
                        frame,x,y,pixels[y*width+x],expected);
                return 1;
            }
        }
        CHECK(so_aot_resume(m,0xf001));
    }
    CHECK(until_event(m)==SO_AOT_SVC && so_aot_pending_svc(m)==0xf002);
    CHECK(so_aot_stats(m).svc_yields==9);
    CHECK(c->vreg[31][1]==UINT64_C(0xfedcba9876543210));
    CHECK(c->tpidr_el0==0x123400 && c->tpidrro_el0==0x567800 && c->fpcr==0x400000 && c->fpsr==0x10);
    CHECK(so_aot_resume(m,0xf002));
    CHECK(so_aot_set_pc(m,0xdead0000) && so_aot_run(m,1)==SO_AOT_UNCOVERED_PC);
    CHECK(so_aot_set_pc(m,main+1) && so_aot_run(m,1)==SO_AOT_UNALIGNED_PC);
    so_aot_destroy(m);
    /* Real emitted store into an undersized region must halt, not continue to present. */
    m=so_aot_create(lookup,NULL,NULL); CHECK(m);
    CHECK(so_aot_set_pc(m,main) && so_aot_set_reg(m,0,42));
    CHECK(until_event(m)==SO_AOT_SVC && so_aot_pending_svc(m)==0xf000);
    CHECK(so_memory_map(so_aot_memory(m),buffer_va,pixels,4,3));
    so_aot_set_reg(m,0,buffer_va); so_aot_set_reg(m,1,2); so_aot_set_reg(m,2,1);
    CHECK(so_aot_resume(m,0xf000));
    CHECK(until_event(m)==SO_AOT_MEMORY_FAULT);
    CHECK(so_aot_memory(m)->fault_address==buffer_va+4 && so_aot_memory(m)->stores==1);
    CHECK(so_aot_run(m,100)==SO_AOT_MEMORY_FAULT && !so_aot_resume(m,0xf001));
    so_aot_destroy(m);
    m=so_aot_create(lookup,NULL,NULL); CHECK(m);
    c=so_aot_context(m);
    c->host_mem->excl_store(c->host_mem->user,buffer_va,4,1);
    CHECK(so_aot_run(m,1)==SO_AOT_UNSUPPORTED_HOST_OPERATION);
    so_aot_destroy(m);
    m=so_aot_create(lookup,NULL,NULL); CHECK(m);
    c=so_aot_context(m);
    c->host_mem->read_cntpct(c->host_mem->user);
    CHECK(so_aot_run(m,1)==SO_AOT_UNSUPPORTED_HOST_OPERATION);
    so_aot_destroy(m); free(pixels);
    printf("{\"test\":\"suyu_generated_native_aot\",\"passed\":true,\"assertions\":%u,"
           "\"verified_pixels\":327680,\"frames\":4,\"full_suyu_hle\":false}\n",checks);
    return 0;
}
#ifndef SO_SELFTEST_NO_MAIN
int main(void) { return so_aot_selftest(); }
#endif
