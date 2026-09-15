// SPDX-License-Identifier: GPL-2.0-or-later
#include "video_out.h"
#include <orbis/libkernel.h>
#include <orbis/VideoOut.h>
namespace SuyuOrbis {
namespace {
constexpr size_t Alignment=0x200000;
constexpr size_t Stride=(VideoOut::FrameBytes+Alignment-1)&~(Alignment-1);
constexpr size_t Allocation=Stride*2;
constexpr int Timeout=-10001, Invalid=-10002;
}
int VideoOut::Open() {
    if (video_>=0) return Invalid;
    stage_="sceVideoOutOpen";
    video_=sceVideoOutOpen(ORBIS_VIDEO_USER_MAIN,ORBIS_VIDEO_OUT_BUS_MAIN,0,nullptr);
    if (video_<0) return video_;
    stage_="sceKernelAllocateDirectMemory";
    int rc=sceKernelAllocateDirectMemory(0,sceKernelGetDirectMemorySize(),Allocation,Alignment,3,&direct_offset_);
    if (rc<0) return rc;
    allocated_=true;
    stage_="sceKernelMapDirectMemory";
    rc=sceKernelMapDirectMemory(&mapping_,Allocation,0x33,0,direct_offset_,Alignment);
    if (rc<0 || !mapping_) return rc<0?rc:Invalid;
    void* buffers[2]={Buffer(0),Buffer(1)};
    OrbisVideoOutBufferAttribute attribute{};
    sceVideoOutSetBufferAttribute(&attribute,0x80000000,ORBIS_VIDEO_OUT_TILING_MODE_LINEAR,
                                  ORBIS_VIDEO_OUT_ASPECT_RATIO_16_9,Width,Height,Width);
    stage_="sceVideoOutRegisterBuffers";
    registered_=sceVideoOutRegisterBuffers(video_,0,buffers,2,&attribute);
    if (registered_<0) return registered_;
    stage_="sceVideoOutSetFlipRate";
    rc=sceVideoOutSetFlipRate(video_,ORBIS_VIDEO_OUT_FLIP_60HZ);
    if (rc<0) return rc;
    stage_="ready"; return 0;
}
void* VideoOut::Buffer(unsigned index) const {
    if (!mapping_ || index>=2) return nullptr;
    return static_cast<unsigned char*>(mapping_)+Stride*index;
}
int VideoOut::Present(unsigned index,int64_t tag,uint64_t timeout_us) {
    if (video_<0 || registered_<0 || index>=2) return Invalid;
    OrbisVideoOutFlipStatus before{};
    stage_="sceVideoOutGetFlipStatus";
    int rc=sceVideoOutGetFlipStatus(video_,&before);
    if (rc<0) return rc;
    if (before.numFlipPending || (before.num && before.currentBuffer==static_cast<int>(index)))
        return Invalid; // Never overwrite/reuse an in-flight or current scanout buffer.
    stage_="sceVideoOutSubmitFlip";
    rc=sceVideoOutSubmitFlip(video_,index,ORBIS_VIDEO_OUT_FLIP_VSYNC,tag);
    if (rc<0) return rc;
    display_quiescent_=false;
    const uint64_t start=sceKernelGetProcessTime();
    stage_="wait_for_completed_flip";
    do {
        OrbisVideoOutFlipStatus status{};
        rc=sceVideoOutGetFlipStatus(video_,&status);
        if (rc<0) return rc;
        if (status.num>before.num && status.flipArg==tag && status.currentBuffer==static_cast<int>(index)) {
            completed_=status.num; display_quiescent_=true; stage_="frame_presented"; return 0;
        }
        rc=sceKernelUsleep(1000);
        if (rc<0) return rc;
    } while (sceKernelGetProcessTime()-start<timeout_us);
    return Timeout;
}
VideoOut::~VideoOut() {
    /* Do not free backing that might still be scanned out after a failed wait.
     * At process exit the OS reclaims it; an error must not become use-after-free. */
    bool safe=display_quiescent_;
    if (registered_>=0 && sceVideoOutUnregisterBuffers(video_,registered_)<0) safe=false;
    if (video_>=0 && sceVideoOutClose(video_)<0) safe=false;
    if (safe) {
        if (mapping_) sceKernelMunmap(mapping_,Allocation);
        if (allocated_) sceKernelReleaseDirectMemory(direct_offset_,Allocation);
    }
}
}
