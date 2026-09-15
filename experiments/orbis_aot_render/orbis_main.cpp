// SPDX-License-Identifier: GPL-2.0-or-later
#include <cstdio>
#include <cinttypes>
#include <orbis/libkernel.h>
#include "suyu_orbis/aot.h"
#include "suyu_orbis/bundle.h"
#include "video_out.h"
extern "C" int so_aot_selftest(void);
namespace {
constexpr uint64_t RtldBase=0x1000000, MainBase=0x2000000;
constexpr uint64_t BufferBase[2]={0x40000000,0x40400000};
SoBlockFn Lookup(uint64_t pc) { SoBlockFn fn=nullptr; return so_bundle_lookup(pc,&fn)==SO_OK?fn:nullptr; }
uint64_t Counter(void*) {
    /* Same 19.2 MHz domain expected by the generated AArch64 CNTFRQ/CNTPCT pair. */
    const uint64_t us=sceKernelGetProcessTime();
    return (us/5)*96+(us%5)*96/5;
}
int Fail(const char* stage,int code) {
    std::printf("native-aot FAIL %s: %d\n",stage,code);
    FILE* f=std::fopen("/data/aot-failure.json","w");
    if (f) {
        std::fprintf(f,"{\"passed\":false,\"stage\":\"%s\",\"code\":%d}\n",stage,code);
        std::fclose(f);
    }
    return 1;
}
bool Report(unsigned phase,const SuyuOrbis::VideoOut& video,const SoAotMachine* m) {
    char name[80],temporary[84];
    std::snprintf(name,sizeof name,"/data/aot-frame-%u.json",phase);
    std::snprintf(temporary,sizeof temporary,"%s.tmp",name);
    FILE* f=std::fopen(temporary,"w");
    if (!f) return false;
    auto stats=so_aot_stats(m);
    const auto* memory=so_aot_memory(const_cast<SoAotMachine*>(m));
    int rc=std::fprintf(f,"{\"passed\":true,\"test\":\"suyu_generated_aarch64_on_orbis\","
        "\"phase\":%u,\"width\":%u,\"height\":%u,\"completed_flips\":%" PRIu64 ","
        "\"guest_stores\":%" PRIu64 ",\"dispatches\":%" PRIu64 ",\"svc_yields\":%" PRIu64 ","
        "\"runtime_selftests_passed\":true,\"full_suyu_hle\":false,\"switch_gpu\":false,"
        "\"cpu_jit\":false,\"host_draws_pixels\":false,\"protocol\":\"private_test_svc\"}\n",
        phase,video.Width,video.Height,video.CompletedFlips(),memory->stores,stats.dispatches,stats.svc_yields);
    int close_rc=std::fclose(f);
    return rc>0 && close_rc==0 && std::rename(temporary,name)==0;
}
bool Pace(unsigned phase) {
#ifdef SO_AOT_CAPTURE_HANDSHAKE
    /* CI controls capture timing only. This is not a Horizon service stub. */
    char name[80]; std::snprintf(name,sizeof name,"/data/aot-ack-%u",phase);
    const uint64_t start=sceKernelGetProcessTime();
    while (sceKernelGetProcessTime()-start<30000000) {
        FILE* f=std::fopen(name,"r");
        if (f) { std::fclose(f); return true; }
        sceKernelUsleep(10000);
    }
    return false;
#else
    (void)phase;
    return sceKernelUsleep(300000)==0;
#endif
}
}
int main() {
    setvbuf(stdout,nullptr,_IONBF,0);
    if (so_aot_selftest()!=0) return Fail("native_runtime_selftests",-1);
    if (so_bundle_init()!=SO_OK || so_bundle_bind(0,RtldBase)!=SO_OK ||
        so_bundle_bind(1,MainBase)!=SO_OK || so_bundle_seal()!=SO_OK)
        return Fail("bind",-1);
    SuyuOrbis::VideoOut video;
    int rc=video.Open(); if (rc<0) return Fail(video.Stage(),rc);
    SoAotMachine* m=so_aot_create(Lookup,Counter,nullptr);
    if (!m) return Fail("context_allocation",-1);
    struct Guard { SoAotMachine* machine; ~Guard() { so_aot_destroy(machine); } } guard{m};
    for (unsigned i=0;i<2;++i)
        if (!so_memory_map(so_aot_memory(m),BufferBase[i],video.Buffer(i),video.FrameBytes,3))
            return Fail("guest_framebuffer_map",-1);
    so_aot_set_pc(m,RtldBase); so_aot_set_reg(m,16,MainBase);
    unsigned frames=0, back=0;
    bool acquired=false;
    uint64_t deadline_start=sceKernelGetProcessTime();
    for (;;) {
        SoAotResult result=so_aot_run(m,100000);
        if (result==SO_AOT_BUDGET) {
            if (sceKernelGetProcessTime()-deadline_start>30000000) return Fail("guest_dispatch_timeout",-1);
            continue;
        }
        if (result!=SO_AOT_SVC) return Fail(so_aot_result_string(result),static_cast<int>(result));
        const uint64_t svc=so_aot_pending_svc(m);
        switch (svc) {
        case 0xf000:
            if (acquired || frames>=4 || so_aot_get_reg(m,0)!=frames) return Fail("acquire_protocol",-1);
            back=frames&1;
            so_aot_set_reg(m,0,BufferBase[back]);
            so_aot_set_reg(m,1,video.Width); so_aot_set_reg(m,2,video.Height);
            acquired=true;
            break;
        case 0xf001:
            if (!acquired || so_aot_get_reg(m,0)!=frames ||
                so_aot_memory(m)->stores!=static_cast<uint64_t>(frames+1)*video.Width*video.Height)
                return Fail("present_protocol",-1);
            rc=video.Present(back,static_cast<int64_t>(frames+1));
            if (rc<0) return Fail(video.Stage(),rc);
            if (!Report(frames,video,m)) return Fail("write_frame_report",-1);
            std::printf("native-aot: phase %u presented by PS4 VideoOut; guest wrote all pixels\n",frames);
            if (!Pace(frames)) return Fail("capture_ack_timeout",-1);
            ++frames; acquired=false;
            break;
        case 0xf002: {
            if (frames!=4 || acquired) return Fail("finish_protocol",-1);
            FILE* f=std::fopen("/data/aot-complete.json","w");
            if (!f) return Fail("write_completion",-1);
            const int wrote=std::fprintf(f,"{\"passed\":true,\"frames_presented\":4,\"full_suyu_hle\":false,\"switch_gpu\":false}\n");
            const int closed=std::fclose(f);
            if (wrote<=0 || closed!=0) return Fail("close_completion",-1);
            std::puts("native-aot: complete; holding last frame");
            for (;;) sceKernelUsleep(100000);
        }
        default:
            return Fail("unsupported_svc",static_cast<int>(svc));
        }
        if (!so_aot_resume(m,svc)) return Fail("resume",-1);
        deadline_start=sceKernelGetProcessTime();
    }
}
