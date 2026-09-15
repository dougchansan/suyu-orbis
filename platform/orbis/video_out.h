// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <cstddef>
#include <cstdint>
#include <sys/types.h>
namespace SuyuOrbis {
/* Native scanout backend only. It is not a Maxwell/NVN renderer. */
class VideoOut final {
public:
    static constexpr unsigned Width=1280, Height=720;
    static constexpr size_t FrameBytes=static_cast<size_t>(Width)*Height*4;
    VideoOut()=default;
    ~VideoOut();
    VideoOut(const VideoOut&)=delete;
    VideoOut& operator=(const VideoOut&)=delete;
    int Open();
    void* Buffer(unsigned index) const;
    int Present(unsigned index, int64_t frame_tag, uint64_t timeout_us=5000000);
    uint64_t CompletedFlips() const { return completed_; }
    const char* Stage() const { return stage_; }
private:
    int video_=-1;
    int registered_=-1;
    bool allocated_=false;
    bool display_quiescent_=true;
    off_t direct_offset_=0;
    void* mapping_=nullptr;
    uint64_t completed_=0;
    const char* stage_="new";
};
}
