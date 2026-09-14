// SPDX-License-Identifier: GPL-2.0-or-later
#include <cstdio>
#include <cstdint>
#include <cstring>

#include <orbis/libkernel.h>
#include <orbis/VideoOut.h>

namespace {
constexpr uint32_t Width = 1280;
constexpr uint32_t Height = 720;
constexpr uint32_t BytesPerPixel = 4;
constexpr size_t FrameBytes = static_cast<size_t>(Width) * Height * BytesPerPixel;
constexpr size_t Alignment = 0x200000;
constexpr uint32_t PixelFormatA8R8G8B8Srgb = 0x80000000;

uint32_t Pack(uint8_t r, uint8_t g, uint8_t b) {
    return 0xFF000000u | (static_cast<uint32_t>(r) << 16) |
           (static_cast<uint32_t>(g) << 8) | b;
}

void DrawPattern(uint32_t* pixels) {
    static constexpr uint32_t bars[] = {
        0xFFFFFFFFu, // white
        0xFFFFFF00u, // yellow
        0xFF00FFFFu, // cyan
        0xFF00FF00u, // green
        0xFFFF00FFu, // magenta
        0xFFFF0000u, // red
        0xFF0000FFu, // blue
        0xFF101010u, // near black
    };

    for (uint32_t y = 0; y < Height; ++y) {
        for (uint32_t x = 0; x < Width; ++x) {
            const uint32_t bar = (x * 8u) / Width;
            uint32_t color = bars[bar < 8 ? bar : 7];

            // Center checkerboard makes it obvious that pitch, coordinates and
            // individual pixels are all correct rather than just a clear color.
            if (x >= 448 && x < 832 && y >= 216 && y < 504) {
                const bool light = (((x - 448) / 32) ^ ((y - 216) / 32)) & 1;
                color = light ? Pack(245, 245, 245) : Pack(24, 24, 24);
            }

            // 8-pixel white border around the framebuffer.
            if (x < 8 || x >= Width - 8 || y < 8 || y >= Height - 8) {
                color = Pack(255, 255, 255);
            }
            pixels[static_cast<size_t>(y) * Width + x] = color;
        }
    }
}

void WriteReport(bool passed, const char* stage, int code) {
    FILE* f = std::fopen("/data/suyu-orbis-render-probe.json", "w");
    if (!f) {
        return;
    }
    std::fprintf(f,
                 "{\"test\":\"openorbis_cpu_framebuffer\","
                 "\"passed\":%s,\"stage\":\"%s\",\"code\":%d,"
                 "\"width\":%u,\"height\":%u,"
                 "\"pixel_format\":\"A8R8G8B8_SRGB\","
                 "\"renderer\":\"cpu_to_sceVideoOut\"}\n",
                 passed ? "true" : "false", stage, code, Width, Height);
    std::fclose(f);
}

int Fail(const char* stage, int code) {
    std::printf("render-probe: FAIL %s rc=%d (0x%x)\n", stage, code,
                static_cast<unsigned>(code));
    WriteReport(false, stage, code);
    return 1;
}
} // namespace

int main() {
    setvbuf(stdout, nullptr, _IONBF, 0);
    std::puts("render-probe: starting");

    const int video = sceVideoOutOpen(ORBIS_VIDEO_USER_MAIN, ORBIS_VIDEO_OUT_BUS_MAIN, 0, nullptr);
    if (video < 0) {
        return Fail("sceVideoOutOpen", video);
    }

    const size_t requested = FrameBytes * 2;
    const size_t allocation = (requested + Alignment - 1) & ~(Alignment - 1);
    off_t direct_offset = 0;
    int rc = sceKernelAllocateDirectMemory(0, sceKernelGetDirectMemorySize(), allocation,
                                           Alignment, 3, &direct_offset);
    if (rc < 0) {
        return Fail("sceKernelAllocateDirectMemory", rc);
    }

    void* video_memory = nullptr;
    rc = sceKernelMapDirectMemory(&video_memory, allocation, 0x33, 0,
                                  direct_offset, Alignment);
    if (rc < 0 || !video_memory) {
        return Fail("sceKernelMapDirectMemory", rc);
    }

    void* buffers[2] = {
        video_memory,
        static_cast<void*>(static_cast<unsigned char*>(video_memory) + FrameBytes),
    };

    DrawPattern(static_cast<uint32_t*>(buffers[0]));
    std::memcpy(buffers[1], buffers[0], FrameBytes);

    OrbisVideoOutBufferAttribute attr{};
    sceVideoOutSetBufferAttribute(&attr, PixelFormatA8R8G8B8Srgb,
                                  ORBIS_VIDEO_OUT_TILING_MODE_LINEAR,
                                  ORBIS_VIDEO_OUT_ASPECT_RATIO_16_9,
                                  Width, Height, Width);

    rc = sceVideoOutRegisterBuffers(video, 0, buffers, 2, &attr);
    if (rc < 0) {
        return Fail("sceVideoOutRegisterBuffers", rc);
    }

    rc = sceVideoOutSetFlipRate(video, ORBIS_VIDEO_OUT_FLIP_60HZ);
    if (rc < 0) {
        return Fail("sceVideoOutSetFlipRate", rc);
    }

    rc = sceVideoOutSubmitFlip(video, 0, ORBIS_VIDEO_OUT_FLIP_VSYNC, 1);
    if (rc < 0) {
        return Fail("sceVideoOutSubmitFlip", rc);
    }

    WriteReport(true, "frame_submitted", 0);
    std::puts("render-probe: frame submitted; holding test pattern");

    // Keep presenting identical buffers so an automated screenshot has a large
    // stable capture window. The test harness terminates the emulator.
    int buffer_index = 1;
    int64_t flip_arg = 2;
    for (;;) {
        sceKernelUsleep(16667);
        if (sceVideoOutIsFlipPending(video) == 0) {
            const int flip_rc = sceVideoOutSubmitFlip(video, buffer_index,
                                                      ORBIS_VIDEO_OUT_FLIP_VSYNC,
                                                      flip_arg++);
            if (flip_rc == 0) {
                buffer_index ^= 1;
            }
        }
    }
}
