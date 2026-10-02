"""Read, patch and rebuild a Wii WAD (the WiiWare channel container).

Contents are AES-128-CBC encrypted with the title key, which is itself encrypted in the ticket with the
Wii common key.  The common key is not distributed with this project: put it in `common-key.bin`
(16 bytes) next to the patcher, or pass the path.  A rebuilt WAD is fake-signed (the usual
"trucha" trick: pad the TMD/ticket until the SHA-1 of the signed part starts with a zero byte), which is
what homebrew WAD installers and Dolphin accept; the original signature cannot survive any edit.
"""
import hashlib
import struct

from Crypto.Cipher import AES


def _al(n, a):
    return (n + a - 1) & ~(a - 1)


class Wad:
    def __init__(self, data, common_key):
        hs, typ, ver, certlen, _res, tiklen, tmdlen, datalen, footlen = struct.unpack('>I2sH6I', data[:0x20])
        self.type, self.version = typ, ver
        off = _al(hs, 64)
        self.certs = data[off:off + certlen]; off += _al(certlen, 64)
        self.tik = bytearray(data[off:off + tiklen]); off += _al(tiklen, 64)
        self.tmd = bytearray(data[off:off + tmdlen]); off += _al(tmdlen, 64)
        enc = data[off:off + datalen]; off += _al(datalen, 64)
        self.footer = data[off:off + footlen]
        iv = bytes(self.tik[0x1DC:0x1E4]) + bytes(8)
        self.title_key = AES.new(common_key, AES.MODE_CBC, iv).decrypt(bytes(self.tik[0x1BF:0x1CF]))
        self.title_id = bytes(self.tik[0x1DC:0x1E4])
        n = struct.unpack('>H', self.tmd[0x1DE:0x1E0])[0]
        self.boot_index = struct.unpack('>H', self.tmd[0x1E0:0x1E2])[0]
        self.contents = []              # [cid, index, type, plaintext]
        p = 0
        for i in range(n):
            e = 0x1E4 + 36 * i
            cid, idx, ctype, size = struct.unpack('>IHHQ', self.tmd[e:e + 16])
            sha = bytes(self.tmd[e + 16:e + 36])
            blob = enc[p:p + _al(size, 16)]
            p += _al(size, 64)
            plain = AES.new(self.title_key, AES.MODE_CBC, struct.pack('>H', idx) + bytes(14)).decrypt(blob)[:size]
            if hashlib.sha1(plain).digest() != sha:
                raise ValueError('content %d does not match its hash: wrong common key, or a damaged WAD' % idx)
            self.contents.append([cid, idx, ctype, plain])

    @classmethod
    def load(cls, path, key_path):
        key = open(key_path, 'rb').read()
        if len(key) != 16:
            raise ValueError('%s is not a 16-byte common key' % key_path)
        return cls(open(path, 'rb').read(), key)

    def content(self, index):
        return next(c for c in self.contents if c[1] == index)

    def set_content(self, index, data):
        self.content(index)[3] = bytes(data)

    # -- fake signing -------------------------------------------------------------------------------
    @staticmethod
    def _fakesign(buf, pad_off, sig_len=0x140):
        buf[4:4 + 0x100] = bytes(0x100)
        for i in range(1 << 16):
            buf[pad_off:pad_off + 2] = struct.pack('>H', i)
            if hashlib.sha1(bytes(buf[sig_len:])).digest()[0] == 0:
                return
        raise RuntimeError('fakesign failed')

    def build(self):
        tmd, tik = bytearray(self.tmd), bytearray(self.tik)
        body = bytearray()
        for cid, idx, ctype, plain in self.contents:
            e = 0x1E4 + 36 * idx
            tmd[e:e + 16] = struct.pack('>IHHQ', cid, idx, ctype, len(plain))
            tmd[e + 16:e + 36] = hashlib.sha1(plain).digest()
            padded = plain + bytes(_al(len(plain), 16) - len(plain))
            body += AES.new(self.title_key, AES.MODE_CBC, struct.pack('>H', idx) + bytes(14)).encrypt(padded)
            body += bytes(_al(len(body), 64) - len(body))
        datalen = sum(_al(len(c[3]), 16) for c in self.contents) if False else None
        # size field of the data block = encrypted sizes with only 16-byte padding per content, 64-aligned in the file
        datalen = 0
        for c in self.contents:
            datalen = _al(datalen, 64) + _al(len(c[3]), 16)
        self._fakesign(tmd, 0x19A)            # TMD "reserved" field
        self._fakesign(tik, 0x262)            # ticket padding
        hdr = struct.pack('>I2sH6I', 0x20, self.type, self.version, len(self.certs), 0, len(tik), len(tmd),
                          datalen, len(self.footer))
        out = bytearray(hdr)
        for blob in (self.certs, tik, tmd):
            out += bytes(_al(len(out), 64) - len(out))
            out += blob
        out += bytes(_al(len(out), 64) - len(out))
        out += body
        out += bytes(_al(len(out), 64) - len(out))
        out += self.footer
        out += bytes(_al(len(out), 64) - len(out))
        return bytes(out)
