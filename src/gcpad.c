/* GameCube controller (port 1) -> Classic Controller bridge for Fluidity / Hydroventure.
 *
 * Three hooks, one blob each (see hooks.S for the register-saving entry
 * stubs).  The game links the SI library but not PAD, so nothing ever polls
 * the pads: gc_poll() drives the Serial Interface's own auto-polling (the
 * approach is Barrel Blast Patch's, hardware-tested there).  gc_sample() turns
 * the pad's state into a Classic Controller sample in KPAD's ring, and
 * gc_probe() makes WPADProbe report a Classic Controller on channel 0, so the
 * game (and Vague Rant's Classic Controller code) treat the pad as one.
 *
 * Addresses come in as -D macros, resolved per release by anchors.py.
 *
 * This game's KPAD is a newer SDK than City Folk's: the sample ring is at
 * +0x180 with 0x42-byte entries (next-write index +0x17A, count +0x17B, an
 * optional extension ring through +0x5A0/+0x5A4), and the data-format byte
 * of a sample is at +0x40.
 */
typedef unsigned int u32;
typedef signed int s32;
typedef unsigned short u16;
typedef signed short s16;
typedef unsigned char u8;
typedef signed char s8;

#define R32(a) (*(volatile u32 *)(a))
#define SI_OUT0   (0xCD006400u)
#define SI_IN0H   (0xCD006404u)
#define SI_IN0L   (0xCD006408u)
#define SI_POLL   (0xCD006430u)
#define SI_COMCSR (0xCD006434u)
#define SI_SR     (0xCD006438u)

struct st {
    u32 probe_tb;   /* last SIGetType */
    u32 busy_tb;    /* when si:: was first seen busy (0 = idle) */
    u8 norep;       /* consecutive frames with NOREP on port 1 */
    u8 ours;        /* the last KPAD sample on channel 0 was ours */
    u32 prev_btn;       /* the Classic Controller buttons of the previous frame's sample */
    u32 n_poll;         /* counters for the test harness: calls of each hook ... */
    u32 n_sample;
    u32 n_sample_ok;    /* ... and how often a pad answered in the sample hook */
    u32 n_probe;
    u32 n_frame;
    u8 connected;       /* we told the game a controller is on channel 0 */
    u32 last_h, last_l; /* the last pad response seen by the sample hook (for the test harness) */
};
#define ST ((volatile struct st *)STATE)

static inline u32 tb(void)
{
    u32 t;
    __asm__ volatile("mftb %0" : "=r"(t));
    return t;
}

/* a valid, error-free pad response on port 1 */
static inline int gc_in(u32 *h, u32 *l)
{
#ifdef DEBUG_FEED
    /* test builds: the pad's response is written to STATE+0x20/0x24 by a debugger */
    if (!R32(STATE + 0x20))
        return 0;
    *h = R32(STATE + 0x20);
    *l = R32(STATE + 0x24);
    return 1;
#endif
    u32 v = R32(SI_IN0H);
    if ((v & 0x80000000u) || !(v & 0x00800000u))
        return 0;
    *h = v;
    *l = R32(SI_IN0L);
    return 1;
}

#if defined(HOOK_FRAME)
static void gc_poll(u32 chan)
{
    volatile u32 *types = (volatile u32 *)SI_TYPES;
    u32 type, sisr, mask, poll;
    int confirmed;
    s32 busy;

    ST->n_poll++;
    if (chan)
        return;

    /* probe the port until a standard pad answers, at most every 0.25 s:
     * probing every frame collided with the pad's own polling on hardware */
    type = types[0];
    confirmed = !(type & 0x80) && (type & 0x18000000u) == 0x08000000u;
    if (!confirmed) {
        u32 now = tb();
        if (now - ST->probe_tb >= 15187500u) {
            ST->probe_tb = now;
            ((u32 (*)(u32))FN_SIGETTYPE)(0);
        }
    }

    /* an unplugged pad latches NOREP; si:: never reads it (no PAD library),
     * so copy a persistent one into the type cache ourselves, which makes
     * SIGetType probe the port again once a pad is plugged back in */
    sisr = R32(SI_SR);
    if (sisr & 0x08000000u) {
        if (ST->norep < 10)
            ST->norep++;
        else
            types[0] = 8;
    } else {
        ST->norep = 0;
    }

    R32(SI_OUT0) = 0x00400300u;                    /* poll command */
    R32(SI_SR) = (sisr & 0x0F0F0F0Fu) | 0x80000000u; /* ack errors, latch OUT */

    type = types[0];
    confirmed = !(type & 0x80) && (type & 0x18000000u) == 0x08000000u;
    mask = confirmed ? 0x88u : 0;                  /* EN0 + VBCPY0 */
    poll = R32(SI_POLL) & ~0xFFu;
    if (!(poll & 0xFF00u))
        poll |= 0x0100u;
    R32(SI_POLL) = poll | mask;
    /* si:: rewrites SIPOLL from its own shadow on every retrace */
    R32(SI_SHADOW) = (R32(SI_SHADOW) & ~0xFFu) | mask;

    /* a pad unplugged mid-transfer leaves si::'s global busy flag wedged
     * (nothing times it out); force it idle after a second */
    busy = (s32)R32(SI_BUSY);
    if (busy == -1) {
        ST->busy_tb = 0;
    } else {
        u32 now = tb();
        if (ST->busy_tb == 0) {
            ST->busy_tb = now | 1;
        } else if (now - ST->busy_tb >= 60750000u) {
            u32 lvl = ((u32 (*)(void))FN_OSDISABLE)();
            R32(SI_BUSY) = (u32)-1;
            R32(SI_COMCSR) = 0x80000000u;
            ((void (*)(u32))FN_OSRESTORE)(lvl);
            ST->busy_tb = 0;
        }
    }
}
/* The game only reads a channel's pad once WPAD's connect callback has marked it connected, and with no Wii
 * Remote that never happens -- KPADRead is not even called.  So once per frame, from the game's own
 * controller update: keep the SI polling going, and when a pad appears (or goes) on port 1 and no real
 * Wii Remote owns channel 0, make the callback the game registered fire, as WPAD would have. */
void gc_frame(void)
{
    u32 h, l;
    u8 *blk;
    s32 status;
    void (*cb)(s32, s32);

    ST->n_frame++;
    gc_poll(0);
    blk = *(u8 **)(WPAD_TBL);
    if (!blk)
        return;
    status = *(s32 *)(blk + 0x900);
    if (gc_in(&h, &l)) {
        if (!ST->connected && status == -1) {
            ST->connected = 1;
            cb = *(void (**)(s32, s32))(blk + 0x8E8);
            if (cb)
                cb(0, 0);
        }
    } else if (ST->connected) {
        ST->connected = 0;
        if (status == -1) {
            cb = *(void (**)(s32, s32))(blk + 0x8E8);
            if (cb)
                cb(0, -1);
        }
    }
}
#endif

#if defined(HOOK_SAMPLE)
/* Classic Controller buttons as WPAD reports them */
#define CL_UP    0x0001
#define CL_LEFT  0x0002
#define CL_ZR    0x0004
#define CL_X     0x0008
#define CL_A     0x0010
#define CL_Y     0x0020
#define CL_B     0x0040
#define CL_ZL    0x0080
#define CL_R     0x0200
#define CL_PLUS  0x0400
#define CL_HOME  0x0800
#define CL_MINUS 0x1000
#define CL_L     0x2000
#define CL_DOWN  0x4000
#define CL_RIGHT 0x8000

#define SMP      0x42           /* bytes per sample */

static inline s16 stick(u32 raw)
{
    s32 v = ((s32)(raw & 0xFF) - 128) * 3;       /* pad ~+-100 -> game +-300 */
    if (v > 308)
        v = 308;
    if (v < -308)
        v = -308;
    return (s16)v;
}

/* GameCube -> Classic Controller, laid out for Fluidity's Classic Controller scheme (Vague Rant):
 * A/B are the game's 2/1, X its A, Y/jump is the shake, L/R/D-pad steer menus and the cloud's wind. */
static __attribute__((noinline)) u32 cc_buttons(u32 h)
{
    u32 b = 0;

    if (h & 0x01000000u) b |= CL_A;          /* A: confirm / interact (2) */
    if (h & 0x02000000u) b |= CL_B;          /* B: cancel / gather (1) */
    if (h & 0x04000000u) b |= CL_X;          /* X: Wii A: zoom out, enter the playroom */
    if (h & 0x08000000u) b |= CL_ZL | CL_ZR; /* Y: shake: jump, rain */
    if (h & 0x10000000u) b |= CL_PLUS;       /* Start: pause / options */
    if (h & 0x00400000u) b |= CL_L;          /* L: left */
    if (h & 0x00200000u) b |= CL_R;          /* R: right */
    if (h & 0x00080000u) b |= CL_UP;
    if (h & 0x00040000u) b |= CL_DOWN;
    if (h & 0x00020000u) b |= CL_RIGHT;
    if (h & 0x00010000u) b |= CL_LEFT;
    if (h & 0x00100000u)                     /* Z: map / tutorial; Start+Z: the HOME Menu */
        b |= (h & 0x10000000u) ? CL_HOME : CL_MINUS;
    if (b & CL_HOME)
        b &= ~CL_PLUS;
    return b;
}

static __attribute__((noinline)) void fill_cc(u8 *s, u32 h, u32 l, u32 b)
{
    *(u16 *)(s + 0x2A) = (u16)b;
    *(s16 *)(s + 0x2C) = stick(h >> 8);      /* control stick x */
    *(s16 *)(s + 0x2E) = stick(h);           /* control stick y */
    *(s16 *)(s + 0x30) = stick(l >> 24);     /* C-stick x */
    *(s16 *)(s + 0x32) = stick(l >> 16);     /* C-stick y */
    s[0x34] = (h & 0x00400000u) ? 180 : 0;   /* digital L / R: the game reads them only as buttons */
    s[0x35] = (h & 0x00200000u) ? 180 : 0;
    s[0x28] = 2;                             /* extension: Classic Controller */
    s[0x29] = 0;                             /* no extension error */
    s[0x40] = 8;                             /* data format: classic + accel + pointer */
}

/* ring slot `i` (the ring is 16 entries, then an optional extension buffer) */
static __attribute__((noinline)) u8 *slot(u8 *k, u32 i)
{
    if (i >= 0x10)
        return *(u8 **)(k + 0x5A0) + (i - 0x10) * SMP;
    return k + 0x180 + i * SMP;
}

/* one fresh Classic Controller sample at ring slot `idx` */
static __attribute__((noinline)) void put_sample(u8 *k, u32 idx, u32 h, u32 l, u32 b)
{
    u8 *p = slot(k, idx);
    u32 i;

    for (i = 0; i < SMP; i++)
        p[i] = 0;
    fill_cc(p, h, l, b);
}

/* One sample per frame left City Folk's controller class with a dead stick (it reads the second entry), and a
 * Wii Remote delivers two or three per read, so we do the same: two samples, the older with the previous
 * frame's buttons (the press and release edges still land in the newest entry) and both with the current
 * sticks. */
void gc_sample(u8 *k, u32 chan)
{
    u32 h, l, b, i, idx, cnt, n;

    ST->n_sample++;
    if (chan || !gc_in(&h, &l))
        return;
    ST->n_sample_ok++;
    ST->last_h = h;
    ST->last_l = l;

    b = cc_buttons(h);
    n = 0x10 + *(u32 *)(k + 0x5A4);   /* ring size */
    idx = k[0x17A];                   /* next slot to write */
    if (idx >= n)
        idx = 0;
    cnt = k[0x17B];
    if (cnt == 0) {
        /* no sample queued: no Wii Remote (ext type 0xFD), a bare one that
         * has not delivered one yet, or our own sample showing through */
        u8 dev = k[0x5C];
        if (!(dev == 0 || dev == 0xFD || ST->ours))
            return;
        put_sample(k, idx, h, l, ST->prev_btn);
        put_sample(k, (idx + 1) % n, h, l, b);
        k[0x17A] = (idx + 2) % n;
        k[0x17B] = 2;
        ST->prev_btn = b;
        ST->ours = 1;
        return;
    }

    /* real samples queued: a bare Wii Remote gets the pad as its extension;
     * a real Nunchuk or Classic Controller is never touched */
    ST->ours = 0;
    ST->prev_btn = b;
    if (cnt > n)
        cnt = n;
    for (i = 0; i < cnt; i++) {
        u8 *s = slot(k, (idx + n - cnt + i) % n);
        if (s[0x28] == 0 || s[0x28] == 0xFD)
            fill_cc(s, h, l, b);
    }
    if (cnt == 1) {
        /* a lone real sample: queue a copy after it so there is a second entry */
        u8 *src = slot(k, (idx + n - 1) % n);
        u8 *dst = slot(k, idx);
        if (src[0x28] == 2) {
            for (i = 0; i < SMP; i++)
                dst[i] = src[i];
            k[0x17A] = (idx + 1) % n;
            k[0x17B] = 2;
        }
    }
}
#endif

#if defined(HOOK_PROBE)
/* WPADProbe(chan, &type): report a Classic Controller on channel 0 while a
 * pad is plugged in, unless the channel already has a real extension */
u32 gc_probe(u32 chan, u32 *type)
{
    u32 h, l;
    u8 *blk;
    u32 t;
    s32 status;

    ST->n_probe++;
    if (chan || !gc_in(&h, &l))
        return 0;
    blk = *(u8 **)(WPAD_TBL + chan * 4);
    t = blk[0x905];
    status = *(s32 *)(blk + 0x900);
    if (status != -1 && (t == 1 || t == 2))
        return 0;
    if (type)
        *type = 2;
    return 1;
}
#endif
