// wheelhook.cpp - 全局鼠标钩子（WH_MOUSE_LL）
// 架构参考 StarPie：
// 1) 右键按下立即吞掉（目标程序永远收不到按下，无卡死/菜单问题）
// 2) 拖动超阈值 -> 通知主线程显示轮盘（手势）
// 3) 抬起：手势 -> 吞掉并通知；普通单击 -> 吞掉并通知主线程重放完整点击
// 4) 重放由主线程用 mouse_event 注入（不在钩子线程内注入）
// 5) 忽略注入事件；_ignoreNext 标志放行重放事件
// 6) event_count 心跳，供主线程做钩子健康检查
#include <windows.h>

typedef void(__stdcall *TriggerCb)(int x, int y, int ox, int oy);
typedef void(__stdcall *ReleaseCb)(int x, int y);
typedef void(__stdcall *NormalUpCb)(int x, int y);
typedef void(__stdcall *LeftClickCb)(int x, int y);
typedef void(__stdcall *MoveCb)(int x, int y);

static TriggerCb g_trigger = nullptr;
static ReleaseCb g_release = nullptr;
static NormalUpCb g_normal_up = nullptr;
static LeftClickCb g_left = nullptr;
static MoveCb g_move = nullptr;

static HHOOK g_hook = nullptr;
static DWORD g_tid = 0;
static HANDLE g_thread = nullptr;
static int g_threshold2 = 14 * 14;
static bool g_r_down = false;
static POINT g_down = {0, 0};
static ULONGLONG g_down_time = 0;
static bool g_wheel_active = false;
static volatile bool g_ignore_down = false;
static volatile bool g_ignore_up = false;
static volatile LONG g_event_count = 0;

#define LLMHF_INJECTED 0x00000001
#define WATCHDOG_MS 10000

static bool handle_event(int nCode, WPARAM wParam, LPARAM lParam) {
    if (nCode != HC_ACTION || lParam == 0) return false;
    InterlockedIncrement(&g_event_count);  // 心跳：任何事件都计数
    MSLLHOOKSTRUCT *ms = reinterpret_cast<MSLLHOOKSTRUCT *>(lParam);
    int x = ms->pt.x;
    int y = ms->pt.y;

    // _ignoreNext 标志：放行紧随其后的真实事件（备用机制）
    if (wParam == WM_RBUTTONDOWN && g_ignore_down) {
        g_ignore_down = false;
        return false;
    }
    if (wParam == WM_RBUTTONUP && g_ignore_up) {
        g_ignore_up = false;
        return false;
    }
    // 重放事件（带注入标志）：放行，不进入手势状态机
    if (ms->flags & LLMHF_INJECTED) {
        return false;
    }

    // 看门狗：按下超过 10 秒未抬起，复位状态
    if (g_r_down && !g_wheel_active && g_down_time &&
        GetTickCount64() - g_down_time > WATCHDOG_MS) {
        g_r_down = false;
        g_down_time = 0;
    }

    switch (wParam) {
        case WM_LBUTTONDOWN:
            if (g_left) g_left(x, y);
            return false;
        case WM_RBUTTONDOWN:
            // 立即吞掉按下：目标程序永远收不到，避免卡死/菜单
            g_r_down = true;
            g_down = ms->pt;
            g_down_time = GetTickCount64();
            return true;
        case WM_RBUTTONUP:
            if (g_wheel_active) {
                g_wheel_active = false;
                g_r_down = false;
                g_down_time = 0;
                if (g_release) g_release(x, y);
                return true;  // 手势：吞掉
            }
            if (g_r_down) {
                g_r_down = false;
                g_down_time = 0;
                if (g_normal_up) g_normal_up(x, y);  // 普通单击：通知主线程重放
                return true;  // 吞掉真实抬起
            }
            return false;
        case WM_MOUSEMOVE:
            if (g_wheel_active) {
                if (g_move) g_move(x, y);  // 手势期间驱动轮盘高亮
            } else if (g_r_down) {
                int dx = x - g_down.x;
                int dy = y - g_down.y;
                if (dx * dx + dy * dy >= g_threshold2) {
                    g_wheel_active = true;
                    if (g_trigger) g_trigger(x, y, g_down.x, g_down.y);
                }
            }
            return false;
    }
    return false;
}

static LRESULT CALLBACK hook_proc(int nCode, WPARAM wParam, LPARAM lParam) {
    bool swallow = false;
    try {
        swallow = handle_event(nCode, wParam, lParam);
    } catch (...) {
    }
    if (swallow) return 1;
    return CallNextHookEx(g_hook, nCode, wParam, lParam);
}

static DWORD WINAPI hook_thread(LPVOID) {
    g_tid = GetCurrentThreadId();
    g_hook = SetWindowsHookExW(WH_MOUSE_LL, hook_proc, nullptr, 0);
    MSG msg;
    while (GetMessageW(&msg, nullptr, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    if (g_hook) {
        UnhookWindowsHookEx(g_hook);
        g_hook = nullptr;
    }
    g_tid = 0;
    return 0;
}

extern "C" __declspec(dllexport) void configure(
    TriggerCb t, ReleaseCb r, NormalUpCb n, LeftClickCb l, MoveCb m) {
    g_trigger = t;
    g_release = r;
    g_normal_up = n;
    g_left = l;
    g_move = m;
}

extern "C" __declspec(dllexport) int start_hook(
    TriggerCb t, ReleaseCb r, NormalUpCb n, LeftClickCb l, MoveCb m) {
    configure(t, r, n, l, m);
    g_thread = CreateThread(nullptr, 0, hook_thread, nullptr, 0, nullptr);
    return g_thread ? 1 : 0;
}

extern "C" __declspec(dllexport) void stop_hook() {
    if (g_hook) {
        UnhookWindowsHookEx(g_hook);
        g_hook = nullptr;
    }
    if (g_tid) {
        PostThreadMessageW(g_tid, WM_QUIT, 0, 0);
    }
    if (g_thread) {
        WaitForSingleObject(g_thread, 3000);
        CloseHandle(g_thread);
        g_thread = nullptr;
    }
}

extern "C" __declspec(dllexport) void set_drag_threshold(int px) {
    int v = px < 4 ? 4 : px;
    g_threshold2 = v * v;
}

extern "C" __declspec(dllexport) void set_ignore_next_click() {
    g_ignore_down = true;
    g_ignore_up = true;
}

extern "C" __declspec(dllexport) long get_event_count() {
    return g_event_count;
}

// 测试用：模拟消息，返回 1 表示该事件会被吞掉
extern "C" __declspec(dllexport) int debug_feed(int wParam, int x, int y, int flags) {
    MSLLHOOKSTRUCT ms = {};
    ms.pt.x = x;
    ms.pt.y = y;
    ms.flags = static_cast<DWORD>(flags);
    return handle_event(HC_ACTION, wParam, reinterpret_cast<LPARAM>(&ms)) ? 1 : 0;
}
