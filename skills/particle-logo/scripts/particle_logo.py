#!/usr/bin/env python3
"""
Particle Logo Convergence — image2pipe → FFmpeg
Claude Sonnet 4.6

修复：
- 自动检测背景色，canvas 初始化为背景色
- 粒子保留 logo 原始颜色
- 粒子收敛后，logo 以"胶片跳帧"感过渡到原图
- 音乐配合 reveal 节奏
"""

import argparse, io, math, wave, random, subprocess, sys
from pathlib import Path

import numpy as np
from PIL import Image

# ════════════════════════════════════════
#  CONFIG
# ════════════════════════════════════════
LOGO_FILE      = "logo.png"   # 可被命令行参数覆盖
OUTPUT_FILE    = "output.mp4" # 可被命令行参数覆盖

N_PARTICLES    = 10_000
DURATION       = 6.0          # 总时长缩短
FPS            = 60

W, H           = 1920, 1080   # 可被命令行或自动推断覆盖
LOGO_FIT_W     = 1540         # 动态计算，见 main()
LOGO_FIT_H     = 880
FG_MIN_DIST    = None  # None = 自动 Otsu 阈值；也可手动指定数值（0-255 空间欧氏距离）

MAX_SPEED      = 34.0          # 更快收敛
MAX_FORCE      = 2.2           # 更强引力
ARRIVAL_RADIUS = 120
DAMPING        = 0.88

TRAIL_DECAY    = 0.65
NOISE_STRENGTH = 2.0           # 略减扰动，收敛更干净
PARTICLE_ALPHA = 0.75

# 时间节点：3.5s 粒子收敛完毕，叮咚，logo 跳出
CONVERGE_T     = 3.5
REVEAL_START   = 3.5           # 未使用，保留兼容
REVEAL_FULL    = 3.5

SAMPLE_RATE    = 44100
# ════════════════════════════════════════

random.seed(0)
np.random.seed(0)


# ── 辅助 ──────────────────────────────────────────────────────────────────────
def ease_in_out(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)

def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3

def ease_in(t):
    t = max(0.0, min(1.0, t))
    return t ** 3


# ── 1. Logo 处理 ──────────────────────────────────────────────────────────────
def load_logo(bg_color_cli=None):
    print(f"  Loading {LOGO_FILE} ...")
    img = Image.open(LOGO_FILE)

    # ── 透明通道处理 ────────────────────────────────────────
    has_alpha = img.mode in ("RGBA", "LA", "PA")
    if has_alpha:
        img = img.convert("RGBA")
        alpha_arr = np.array(img)[:, :, 3]   # 0-255
        # 透明背景：把 logo 合成到白底，背景色固定为白色
        white_bg = Image.new("RGB", img.size, (255, 255, 255))
        white_bg.paste(img, mask=img.split()[3])
        img = white_bg
        bg_color_override = np.array([255.0, 255.0, 255.0])
    else:
        img = img.convert("RGB")
        alpha_arr = None
        bg_color_override = None

    scale = min(LOGO_FIT_W / img.width, LOGO_FIT_H / img.height)
    lw = int(img.width  * scale)
    lh = int(img.height * scale)
    img = img.resize((lw, lh), Image.LANCZOS)
    arr = np.array(img).astype(float)
    if alpha_arr is not None:
        alpha_arr = np.array(
            Image.fromarray(alpha_arr).resize((lw, lh), Image.LANCZOS)
        ).astype(float)

    # ── 自动检测背景色（四角均值，透明图用白色覆盖）───────
    corners = np.stack([arr[0,0], arr[0,-1], arr[-1,0], arr[-1,-1]])
    if bg_color_cli is not None:
        bg_color = bg_color_cli
    elif bg_color_override is not None:
        bg_color = bg_color_override
    else:
        bg_color = corners.mean(axis=0)
    print(f"  Auto BG color: RGB({bg_color[0]:.0f},{bg_color[1]:.0f},{bg_color[2]:.0f})")

    ox = (W - lw) // 2
    oy = (H - lh) // 2

    # ── 前景掩码：自动 Otsu 阈值 ──────────────────────────
    # 计算每个像素与背景色的欧氏距离
    if has_alpha and alpha_arr is not None:
        # 优先使用 alpha 通道：最精准
        mask = alpha_arr > 30
        print(f"  Foreground detection: alpha channel")
    else:
        dist = np.sqrt(((arr - bg_color) ** 2).sum(axis=2))   # shape (lh, lw)

        # Otsu 阈值：自动找前景/背景最优分割点
        threshold = FG_MIN_DIST
        if threshold is None:
            hist, edges = np.histogram(dist.ravel(), bins=256, range=(0, dist.max() + 1e-6))
            total = hist.sum()
            best_var, threshold = 0.0, edges[1]
            w0 = sum0 = 0.0
            for i, (h, e) in enumerate(zip(hist, edges[:-1])):
                w0   += h
                w1    = total - w0
                if w0 == 0 or w1 == 0:
                    continue
                sum0 += h * e
                mu0   = sum0 / w0
                mu1   = (dist.sum() - sum0) / w1
                var   = w0 * w1 * (mu0 - mu1) ** 2
                if var > best_var:
                    best_var, threshold = var, e
            print(f"  Foreground detection: Otsu threshold = {threshold:.1f}")
        else:
            print(f"  Foreground detection: manual threshold = {threshold:.1f}")

        mask = dist > threshold

    ys, xs = np.where(mask)
    if len(xs) == 0:
        sys.exit("ERROR: no foreground pixels found — try lowering FG_MIN_DIST")

    world_xs = xs + ox
    world_ys = ys + oy
    targets  = np.column_stack([world_xs, world_ys]).astype(float)

    # 粒子颜色 = logo 原始颜色
    colors = arr[ys, xs].copy()               # shape (N_targets, 3), 0-255

    # 预计算 logo 全画布（reveal 阶段用）
    logo_canvas = np.full((H, W, 3), bg_color, dtype=float)
    logo_canvas[oy:oy+lh, ox:ox+lw] = arr

    print(f"  Logo size: {lw}×{lh}, offset: ({ox},{oy}), targets: {len(targets):,}")
    return targets, colors, bg_color, logo_canvas


# ── 2. 粒子系统 ───────────────────────────────────────────────────────────────
class ParticleSystem:
    def __init__(self, targets, colors, bg_color):
        N = N_PARTICLES
        idx = np.random.randint(0, len(targets), N)
        self.targets = targets[idx]
        self.colors  = colors[idx].astype(float)   # 0-255，保留原色

        # 初始位置：混合三种生成方式
        spawn = np.random.randint(0, 3, N)
        pos   = np.empty((N, 2))

        m0 = spawn == 0   # 全画面随机
        pos[m0] = np.random.rand(m0.sum(), 2) * [W, H]

        m1 = spawn == 1   # 四边飞入
        n1 = m1.sum()
        edge = np.random.randint(0, 4, n1)
        ep   = np.empty((n1, 2))
        ep[edge==0] = np.c_[np.random.rand((edge==0).sum())*W, np.full((edge==0).sum(), -60)]
        ep[edge==1] = np.c_[np.random.rand((edge==1).sum())*W, np.full((edge==1).sum(), H+60)]
        ep[edge==2] = np.c_[np.full((edge==2).sum(), -60), np.random.rand((edge==2).sum())*H]
        ep[edge==3] = np.c_[np.full((edge==3).sum(), W+60), np.random.rand((edge==3).sum())*H]
        pos[m1] = ep

        m2 = spawn == 2   # 中心爆散
        n2 = m2.sum()
        ang = np.random.rand(n2) * 2 * np.pi
        rad = np.random.rand(n2) * 600 + 200
        pos[m2] = np.c_[W/2 + np.cos(ang)*rad, H/2 + np.sin(ang)*rad]

        self.pos = pos.astype(float)
        tc  = np.array([W/2, H/2]) - self.pos
        tc  = tc / (np.linalg.norm(tc, axis=1, keepdims=True) + 1e-8)
        self.vel = tc * np.random.rand(N,1) * 2.0 + np.random.randn(N,2) * 1.5

        self.noise_phase = np.random.rand(N, 2) * 100.0
        self.arrived     = np.zeros(N, dtype=bool)

    def update(self, t):
        if t < 2.0:
            seek_k  = ease_out(t / 2.0) * 0.25
            noise_k = NOISE_STRENGTH
            max_spd = MAX_SPEED * 0.6
        elif t < CONVERGE_T:
            p       = (t - 2.0) / (CONVERGE_T - 2.0)
            seek_k  = 0.25 + ease_in_out(p) * 0.75
            noise_k = NOISE_STRENGTH * (1.0 - ease_in_out(p) * 0.90)
            max_spd = MAX_SPEED
        else:
            seek_k  = 1.0
            noise_k = 0.12
            max_spd = MAX_SPEED * 0.25

        diff  = self.targets - self.pos
        dist  = np.linalg.norm(diff, axis=1, keepdims=True)
        speed = np.where(dist < ARRIVAL_RADIUS,
                         max_spd * dist / ARRIVAL_RADIUS, max_spd)
        desired = diff / (dist + 1e-8) * speed * seek_k
        steer   = desired - self.vel
        sm = np.linalg.norm(steer, axis=1, keepdims=True)
        steer = steer / (sm + 1e-8) * np.minimum(sm, MAX_FORCE * seek_k)

        # Smooth noise walk
        self.noise_phase += 0.08
        nx = np.sin(self.noise_phase[:,0]*1.3) * np.cos(self.noise_phase[:,1]*0.7)
        ny = np.cos(self.noise_phase[:,0]*0.9) * np.sin(self.noise_phase[:,1]*1.1)
        noise = np.c_[nx, ny] * noise_k

        self.vel = self.vel + steer + noise * 0.016
        vm = np.linalg.norm(self.vel, axis=1, keepdims=True)
        self.vel = self.vel / (vm + 1e-8) * np.minimum(vm, max_spd)
        damp = np.where(dist < ARRIVAL_RADIUS, DAMPING * 0.88, DAMPING)
        self.vel = self.vel * damp

        # 到达后弹簧微振
        arrived_now = dist[:,0] < 3.0
        self.arrived |= arrived_now
        if self.arrived.any():
            spring = -0.08 * (self.pos[self.arrived] - self.targets[self.arrived])
            self.vel[self.arrived] = self.vel[self.arrived] * 0.5 + spring

        self.pos += self.vel


# ── 3. 粒子渲染（alpha 合成，支持任意背景色）─────────────────────────────────
def render_particles(canvas: np.ndarray, ps: ParticleSystem,
                     bg_color: np.ndarray) -> np.ndarray:
    # 拖尾：衰减向背景色
    canvas[:] = canvas * TRAIL_DECAY + bg_color * (1 - TRAIL_DECAY)

    pos = ps.pos
    col = ps.colors.copy()                         # 0-255

    # 速度越快粒子越不透明（运动感）
    spd = np.linalg.norm(ps.vel, axis=1)
    alpha_per_particle = PARTICLE_ALPHA * (0.5 + np.clip(spd / MAX_SPEED, 0, 1) * 0.5)

    px = pos[:,0].astype(int)
    py = pos[:,1].astype(int)
    valid = (px >= 1) & (px < W-1) & (py >= 1) & (py < H-1)
    px, py, c, a = px[valid], py[valid], col[valid], alpha_per_particle[valid]

    # 用影响力图做正确的 alpha 混合
    inf_col = np.zeros((H, W, 3), dtype=float)
    inf_a   = np.zeros((H, W),    dtype=float)
    np.add.at(inf_col, (py, px), c * a[:,np.newaxis])
    np.add.at(inf_a,   (py, px), a)

    # bloom（邻域）
    b = 0.28
    for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
        vx, vy = (px+dx).clip(0,W-1), (py+dy).clip(0,H-1)
        np.add.at(inf_col, (vy, vx), c * a[:,np.newaxis] * b)
        np.add.at(inf_a,   (vy, vx), a * b)

    # 混合到 canvas
    blend = np.clip(inf_a, 0, 1)[:,:,np.newaxis]
    avg   = np.where(inf_a[:,:,np.newaxis] > 0,
                     inf_col / inf_a[:,:,np.newaxis].clip(1e-6, None),
                     canvas)
    canvas[:] = canvas * (1 - blend) + avg * blend
    return canvas


# ── 4. Reveal alpha 序列（胶片跳帧感）────────────────────────────────────────
def build_reveal_alphas(total_frames: int) -> np.ndarray:
    """叮咚瞬间切换，之后保持 1.0。"""
    ding_f = int(CONVERGE_T * FPS)
    alphas = np.zeros(total_frames)
    alphas[ding_f:] = 1.0
    return alphas


def build_brightness_bounce(total_frames: int) -> np.ndarray:
    """叮咚瞬间过曝，然后弹簧衰减回 1.0，产生轻弹跳感。"""
    ding_f   = int(CONVERGE_T * FPS)
    bounce   = np.ones(total_frames)
    overshoot = 1.28          # 瞬间过曝倍数
    decay     = 0.38          # 指数衰减速率（越大越快稳定）
    spring_k  = 1.15          # 振荡频率
    settle    = 30            # 稳定所需帧数

    for df in range(settle):
        f = ding_f + df
        if f >= total_frames:
            break
        # 弹簧公式：1 + A·e^(-decay·df)·cos(spring_k·df)
        extra = (overshoot - 1.0) * math.exp(-decay * df) * math.cos(spring_k * df)
        bounce[f] = 1.0 + extra

    return bounce


# ── 5. 音频合成 ───────────────────────────────────────────────────────────────
def generate_audio(path: Path):
    """
    0 → CONVERGE_T (5s): 持续 build-up，全层叠加，无死区
      - 颗粒纹理（全程，密度随时间增加）
      - 低频嗡鸣 drone（全程，音量渐增）
      - 上扫频 sweep（全程 0→5s，振幅渐增）
      - 加速节拍脉冲（全程，频率 1→3 Hz，振幅渐增）
      - 粉红噪声层（全程，细微底噪增强临场感）
    CONVERGE_T: 叮咚（清脆单音 + 低频冲击）
    CONVERGE_T → DURATION: A大调和弦驻留 + 混响淡出
    """
    print("  Generating audio ...")
    SR  = SAMPLE_RATE
    n   = int(SR * DURATION)
    t   = np.linspace(0, DURATION, n, endpoint=False)
    mix = np.zeros(n)

    # 时间归一化 0→1（仅在 0→CONVERGE_T 段）
    t_norm = np.clip(t / CONVERGE_T, 0, 1)   # 线性 0→1 across build window

    def seg(s, e):
        """返回 [s, e) 段的样本索引"""
        return int(s * SR), min(n, int(e * SR))

    # ── 颗粒纹理：全程 0→CONVERGE_T，密度随时间增加 ────────
    # 前半段稀疏高频，后半段密集中频
    n_grains_early = 300   # 0-2.5s
    n_grains_late  = 600   # 2.5-5s
    for i in range(n_grains_early + n_grains_late):
        if i < n_grains_early:
            t0   = random.uniform(0, 2.5)
            freq = random.uniform(800, 8000)
            amp  = random.uniform(0.025, 0.07)
        else:
            t0   = random.uniform(2.5, CONVERGE_T)
            freq = random.uniform(400, 5000)
            amp  = random.uniform(0.04, 0.11)
        dur_ = random.uniform(0.008, 0.06)
        si   = int(t0 * SR)
        ei   = min(n, si + int(dur_ * SR))
        if ei <= si: continue
        bt   = np.linspace(0, 1, ei - si)
        mix[si:ei] += amp * np.sin(2*np.pi*freq * bt * (ei-si)/SR) * np.sin(bt * np.pi)

    # ── 低频 drone：全程，0.018→0.045 渐增 ──────────────────
    drone_env = 0.018 + 0.027 * t_norm
    mix += drone_env * np.sin(2*np.pi * 41 * t)
    mix += drone_env * 0.55 * np.sin(2*np.pi * 55 * t)
    mix += drone_env * 0.30 * np.sin(2*np.pi * 82 * t)

    # ── 上扫频 sweep 180→1320 Hz：全程 0→CONVERGE_T ─────────
    sw_si, sw_ei = seg(0, CONVERGE_T)
    sw_len = sw_ei - sw_si
    sw_tau  = np.linspace(0, 1, sw_len)
    sw_f    = 180 * (2 ** (sw_tau * 2.87))          # 180→1320 Hz (2.87 octaves)
    sw_ph   = np.cumsum(sw_f / SR * 2 * np.pi)
    sw_amp  = 0.018 + 0.065 * sw_tau                # 0.018 → 0.083
    mix[sw_si:sw_ei] += np.sin(sw_ph) * sw_amp

    # 二次谐波让扫频更丰满
    sw_f2   = sw_f * 2
    sw_ph2  = np.cumsum(sw_f2 / SR * 2 * np.pi)
    mix[sw_si:sw_ei] += np.sin(sw_ph2) * sw_amp * 0.35

    # ── 节拍脉冲：全程，1 Hz → 3 Hz 加速 ───────────────────
    bp_si, bp_ei = seg(0, CONVERGE_T)
    bp_len = bp_ei - bp_si
    bp_tau  = np.linspace(0, 1, bp_len)
    bp_f    = 1.0 + 2.0 * bp_tau                    # 1→3 Hz
    bp_ph   = np.cumsum(bp_f / SR * 2 * np.pi)
    bp_amp  = 0.08 + 0.18 * bp_tau                  # 0.08→0.26
    bp      = np.clip(np.sin(bp_ph), 0, 1) ** 2 * bp_amp
    mix[bp_si:bp_ei] += bp

    # 节拍伴随的低鼓感
    kick_amp = 0.04 + 0.10 * bp_tau
    kick_env = np.clip(np.sin(bp_ph), 0, 1) ** 4
    mix[bp_si:bp_ei] += kick_env * kick_amp * np.sin(2*np.pi * 65 * np.linspace(0, CONVERGE_T, bp_len))

    # ── 粉红噪声底层：全程，细微增强临场感 ─────────────────
    white = np.random.randn(n)
    # 简单 pink 近似：低通 + 混合
    b0=b1=b2=0.0
    pink = np.zeros(n)
    for i in range(n):
        w = white[i]
        b0 = 0.99765*b0 + w*0.0990460
        b1 = 0.96300*b1 + w*0.2965164
        b2 = 0.57000*b2 + w*0.1848000
        pink[i] = b0+b1+b2 + w*0.1848
    pink_env = (0.006 + 0.012 * t_norm) * (t_norm < 1.0)
    mix += pink * pink_env

    # ── 最后 0.5s 前：高频颤音冲刺 ────────────────────────
    h_si, h_ei = seg(CONVERGE_T - 0.6, CONVERGE_T)
    h_len = h_ei - h_si
    h_tau = np.linspace(0, 1, h_len)
    mix[h_si:h_ei] += 0.045 * np.sin(2*np.pi * 3400 * np.linspace(0, 0.6, h_len)) * h_tau

    # ── 叮咚（CONVERGE_T）：清脆单音 + 低频冲击 ─────────────
    i_si = int(CONVERGE_T * SR)

    # 低频冲击（短促 kick）
    kick_t = np.linspace(0, 1, int(SR * 0.35))
    bd = 0.55 * np.sin(2*np.pi * (95 - 60*kick_t) * kick_t) * np.exp(-kick_t * 14)
    ei = min(n, i_si + len(bd))
    mix[i_si:ei] += bd[:ei-i_si]

    # 叮咚主音（C6 + 泛音）
    ding_len = int(SR * 1.0)
    ding_tau = np.linspace(0, 1, ding_len)
    ding = (0.38 * np.sin(2*np.pi * 1047 * ding_tau)   # C6
          + 0.18 * np.sin(2*np.pi * 1568 * ding_tau)   # G6
          + 0.09 * np.sin(2*np.pi * 2093 * ding_tau)   # C7
          + 0.04 * np.sin(2*np.pi * 3136 * ding_tau))  # G7
    ding *= np.exp(-ding_tau * 5.5)
    ei = min(n, i_si + ding_len)
    mix[i_si:ei] += ding[:ei-i_si]

    # ── 和弦驻留 (CONVERGE_T → DURATION) ───────────────────
    cs, ce = seg(CONVERGE_T + 0.05, DURATION)
    c_len  = ce - cs
    c_tau  = np.linspace(0, 1, c_len)
    # A大调和弦：A3 C#4 E4 A4 E5
    chord = [(220,0.060),(277.18,0.050),(329.63,0.044),(440,0.030),(659.25,0.022)]
    c_env  = (1 - np.exp(-c_tau * 8)) * np.exp(-c_tau * 0.9)   # attack + gentle decay
    c_t    = np.linspace(CONVERGE_T + 0.05, DURATION, c_len)
    for cf, ca in chord:
        mix[cs:ce] += ca * np.sin(2*np.pi * cf * c_t) * c_env
        mix[cs:ce] += ca * 0.18 * np.sin(2*np.pi * cf * 2 * c_t) * c_env

    # ── 混响（简单 multi-tap echo）────────────────────────
    for delay_s, decay in [(0.18, 0.28), (0.32, 0.16), (0.50, 0.09)]:
        delay_smp = int(SR * delay_s)
        if delay_smp < n:
            echo = np.zeros(n)
            echo[delay_smp:] = mix[:-delay_smp] * decay
            mix += echo

    # ── 归一化 ─────────────────────────────────────────────
    mx = np.max(np.abs(mix))
    if mx > 0:
        mix = mix / mx * 0.88

    with wave.open(str(path), 'w') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes((mix * 32767).astype(np.int16).tobytes())
    print(f"  Audio saved: {path}")


# ── 6. 主循环 ─────────────────────────────────────────────────────────────────
def main():
    global LOGO_FILE, OUTPUT_FILE, W, H, LOGO_FIT_W, LOGO_FIT_H, DURATION, CONVERGE_T, REVEAL_START, REVEAL_FULL, N_PARTICLES, FPS

    parser = argparse.ArgumentParser(
        description="Particle Logo Convergence",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("logo",   nargs="?", default=LOGO_FILE,
                        help="输入图片路径（默认 logo.png）")
    parser.add_argument("output", nargs="?", default=OUTPUT_FILE,
                        help="输出视频路径（默认 output.mp4）")
    parser.add_argument("--size", default=None,
                        help="视频尺寸，例如：\n"
                             "  1920x1080  横版\n"
                             "  1080x1080  正方形\n"
                             "  1080x1920  竖版\n"
                             "  1080       等同 1080x1080\n"
                             "不传则根据图片长宽自动选择")
    parser.add_argument("--duration", type=float, default=None,
                        help="视频时长（秒），默认 6.0\n"
                             "  汇聚阶段占 ~58%%，展示阶段占 ~42%%\n"
                             "  最小 3.0 秒，最大 30.0 秒")
    parser.add_argument("--particles", type=int, default=None,
                        help="粒子数量，默认 10000\n"
                             "  范围 1000-50000\n"
                             "  更多粒子 = 更细腻但更慢")
    parser.add_argument("--fps", type=int, default=None, choices=[30, 60],
                        help="帧率，默认 60\n"
                             "  30 = 文件更小，60 = 更流畅")
    parser.add_argument("--bg", default=None,
                        help="背景色，默认 auto（自动检测）\n"
                             "  white / black / #RRGGBB")
    parser.add_argument("--no-audio", action="store_true",
                        help="跳过音频合成，仅输出视频")
    args = parser.parse_args()
    LOGO_FILE   = args.logo
    OUTPUT_FILE = args.output

    # ── 解析时长 ──────────────────────────────────────────────
    if args.duration is not None:
        DURATION = max(3.0, min(30.0, args.duration))
    CONVERGE_T   = DURATION * 0.583   # 保持 3.5/6.0 的比例
    REVEAL_START = CONVERGE_T
    REVEAL_FULL  = CONVERGE_T

    # ── 解析粒子数 ────────────────────────────────────────────
    if args.particles is not None:
        N_PARTICLES = max(1000, min(50000, args.particles))

    # ── 解析帧率 ──────────────────────────────────────────────
    if args.fps is not None:
        FPS = args.fps

    # ── 解析背景色 ────────────────────────────────────────────
    bg_color_cli = None
    if args.bg is not None:
        bg = args.bg.strip().lower()
        if bg == "auto":
            bg_color_cli = None
        elif bg == "white":
            bg_color_cli = np.array([255.0, 255.0, 255.0])
        elif bg == "black":
            bg_color_cli = np.array([0.0, 0.0, 0.0])
        elif bg.startswith("#") and len(bg) == 7:
            bg_color_cli = np.array([int(bg[1:3],16), int(bg[3:5],16), int(bg[5:7],16)], dtype=float)
        else:
            sys.exit(f"ERROR: invalid --bg value '{args.bg}'. Use: auto / white / black / #RRGGBB")

    skip_audio = args.no_audio

    # ── 解析视频尺寸 ────────────────────────────────────────
    if args.size:
        # 手动指定
        if 'x' in args.size.lower():
            parts = args.size.lower().split('x')
            W, H = int(parts[0]), int(parts[1])
        else:
            s = int(args.size)
            W, H = s, s
    else:
        # 自动：保持图片原始比例，最长边 ≤ 1920，最短边 ≤ 1080
        with Image.open(LOGO_FILE) as _img:
            iw, ih = _img.size
        scale = min(1920 / max(iw, ih), 1080 / min(iw, ih))
        W, H = round(iw * scale), round(ih * scale)

    # LOGO_FIT 留 80% 边距
    LOGO_FIT_W = int(W * 0.80)
    LOGO_FIT_H = int(H * 0.80)
    # H.264 要求偶数
    W = W + W % 2
    H = H + H % 2

    print("=" * 60)
    print("  Particle Logo Convergence")
    print(f"  {N_PARTICLES:,} particles · {DURATION}s · {FPS}fps · {W}×{H}")
    print("=" * 60)

    audio_path = Path("_particle_audio.wav")
    if not skip_audio:
        generate_audio(audio_path)

    targets, colors, bg_color, logo_canvas = load_logo(bg_color_cli)
    ps = ParticleSystem(targets, colors, bg_color)

    # 画布初始化为背景色
    canvas = np.full((H, W, 3), bg_color, dtype=float)

    total_frames  = int(DURATION * FPS)
    reveal_alphas = build_reveal_alphas(total_frames)
    brightness_bounce = build_brightness_bounce(total_frames)

    ffmpeg_cmd = [
        'ffmpeg', '-y',
        '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-s', f'{W}x{H}', '-pix_fmt', 'rgb24', '-r', str(FPS),
        '-i', 'pipe:0',
    ]
    if not skip_audio:
        ffmpeg_cmd += ['-i', str(audio_path)]
    ffmpeg_cmd += [
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-pix_fmt', 'yuv420p',
    ]
    if not skip_audio:
        ffmpeg_cmd += ['-c:a', 'aac', '-b:a', '192k', '-shortest']
    ffmpeg_cmd.append(OUTPUT_FILE)
    print(f"\n  Streaming {total_frames} frames to FFmpeg ...")
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE,
                            stderr=subprocess.DEVNULL,
                            bufsize=W*H*3*4)

    for f in range(total_frames):
        t = f / FPS

        ps.update(t)
        render_particles(canvas, ps, bg_color)

        # Reveal 叠加：瞬间切换 + 亮度弹跳
        ra = reveal_alphas[f]
        if ra > 0.001:
            br = brightness_bounce[f]
            # 过曝时白底不变，只拉亮有色区域（与背景的差值放大）
            logo_bright = bg_color + (logo_canvas - bg_color) * br
            frame = canvas * (1 - ra) + logo_bright * ra
        else:
            frame = canvas

        try:
            proc.stdin.write(frame.clip(0,255).astype(np.uint8).tobytes())
        except BrokenPipeError:
            break

        if f % 60 == 0:
            stage = "scatter" if t<2 else "converging" if t<CONVERGE_T \
                    else "reveal" if t<REVEAL_FULL else "done"
            print(f"  [{int(f/total_frames*100):3d}%]  {f:4d}/{total_frames}  "
                  f"t={t:.1f}s  ra={ra:.2f}  ({stage})")

    proc.stdin.close()
    ret = proc.wait()
    if not skip_audio:
        audio_path.unlink(missing_ok=True)

    if ret == 0:
        size_mb = Path(OUTPUT_FILE).stat().st_size / 1e6
        print(f"\n{'='*60}\n  Done  →  {OUTPUT_FILE}  ({size_mb:.1f} MB)\n{'='*60}")
    else:
        print(f"  FFmpeg exited {ret}")


if __name__ == '__main__':
    main()
