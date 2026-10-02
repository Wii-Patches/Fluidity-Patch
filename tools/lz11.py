"""LZ11 (0x11) decompression and a simple greedy compressor, as used by the
game's compressed main.dol content in the WAD."""
import struct


def decompress(src):
    if src[0] != 0x11:
        raise ValueError('not LZ11 data')
    size = src[1] | src[2] << 8 | src[3] << 16
    p = 4
    if size == 0:
        size = struct.unpack('<I', src[4:8])[0]
        p = 8
    out = bytearray()
    while len(out) < size:
        flags = src[p]
        p += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                b0 = src[p]
                ind = b0 >> 4
                if ind == 0:
                    ln = ((b0 & 0xF) << 4 | src[p + 1] >> 4) + 0x11
                    disp = ((src[p + 1] & 0xF) << 8 | src[p + 2]) + 1
                    p += 3
                elif ind == 1:
                    ln = ((b0 & 0xF) << 12 | src[p + 1] << 4 | src[p + 2] >> 4) + 0x111
                    disp = ((src[p + 2] & 0xF) << 8 | src[p + 3]) + 1
                    p += 4
                else:
                    ln = ind + 1
                    disp = ((b0 & 0xF) << 8 | src[p + 1]) + 1
                    p += 2
                for _ in range(ln):
                    out.append(out[-disp])
            else:
                out.append(src[p])
                p += 1
    return bytes(out[:size])


def compress(data, chain=24):
    """LZ11 compressor (greedy, hash chains over a 4 KiB window)."""
    n = len(data)
    out = bytearray(b'\x11')
    out += bytes((n & 0xFF, n >> 8 & 0xFF, n >> 16 & 0xFF)) if n < 1 << 24 else b'\0' + struct.pack('<I', n)
    head = {}
    prev = [0] * n          # previous position with the same 3-byte key (or -1)
    WIN, MAXLEN = 0x1000, 0x10110
    pos = 0

    def insert(p):
        if p + 2 < n:
            k = data[p:p + 3]
            prev[p] = head.get(k, -1)
            head[k] = p

    while pos < n:
        flags = 0
        block = bytearray()
        for bit in range(8):
            if pos >= n:
                break
            best_len, best_disp = 0, 0
            if pos + 2 < n:
                k = data[pos:pos + 3]
                cand = head.get(k, -1)
                tries = chain
                limit = min(MAXLEN, n - pos)
                while cand >= 0 and pos - cand <= WIN and tries:
                    tries -= 1
                    ln = 3
                    # extend the match (compare in slices for speed)
                    while ln < limit and data[cand + ln] == data[pos + ln]:
                        ln += 1
                    if ln > best_len:
                        best_len, best_disp = ln, pos - cand
                        if ln == limit:
                            break
                    cand = prev[cand]
            if best_len >= 3:
                flags |= 0x80 >> bit
                d = best_disp - 1
                if best_len <= 0x10:
                    block += bytes(((best_len - 1) << 4 | d >> 8, d & 0xFF))
                elif best_len <= 0x110:
                    l = best_len - 0x11
                    block += bytes((l >> 4, (l & 0xF) << 4 | d >> 8, d & 0xFF))
                else:
                    l = best_len - 0x111
                    block += bytes((0x10 | l >> 12, l >> 4 & 0xFF, (l & 0xF) << 4 | d >> 8, d & 0xFF))
                for q in range(pos, pos + best_len):
                    insert(q)
                pos += best_len
            else:
                block.append(data[pos])
                insert(pos)
                pos += 1
        out.append(flags)
        out += block
    return bytes(out)
