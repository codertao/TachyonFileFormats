# Kaitai Struct definitions

[Kaitai Struct](https://kaitai.io/) (`.ksy`) specs for the Tachyon: The Fringe
file formats reverse-engineered so far. Each one mirrors the `construct` /
hand-rolled parser in `../src`.

| Spec | Format | Source parser | Status |
|------|--------|---------------|--------|
| [`pff.ksy`](pff.ksy) | PFF asset archive | `src/pff.py` | Complete — parses straight from file |
| [`spd.ksy`](spd.ksy) | SPD / `.SPX` sector file | `src/spd.py`, `src/spxtrig.py` | Core sections + mission trigger table, dialog/scene lists complete; some header dwords + record tails left as unknowns. Parses all 302 shipped SPX files |
| [`cbin.ksy`](cbin.ksy) | CBIN config container | `src/cbin.py` | Header only (see caveats) |
| [`pak.ksy`](pak.ksy) | PAK (`3DPK`) 3D model | `src/pak.py` | Complete structure: LODs, parts, 3DO1 meshes, collision, states, textures. Texture pixels stay RLE-compressed (see caveats). Some material/part bytes unknown |

## Using these

Paste a spec into the [Kaitai Web IDE](https://ide.kaitai.io/) and drop a
sample file on it, or compile to a parser:

```sh
kaitai-struct-compiler -t python pff.ksy    # also: java, cpp_stl, javascript, go, ...
```

## CBIN caveats

`cbin.ksy` can only parse the 20-byte header directly, for two reasons Kaitai's
language genuinely can't bridge:

1. **Custom stream cipher.** Everything after the header is encrypted with a
   rotating-XOR keystream (`k = rotl32(k, 7); plaintext = c ^ (k & 0xFF)`).
   Kaitai's `process:` only offers a fixed repeating XOR and `rol`/`ror`, not a
   per-byte evolving keystream. Decrypt first (see `cbin.decrypt_cbin` in
   `../src/cbin.py`), then apply the `decrypted` type from the spec.
2. **Summed array lengths.** On the decrypted stream the `items` and `params`
   sections are sized by *sums* over earlier arrays, and the KSY expression
   language has no fold/sum. The `groups`, `group_count`, and (via
   `text_offset`) the string table are expressible; the two summed arrays are
   documented inline and must be walked manually.

The `.SPX` placement records are variable-stride but *self-describing* (each
record's `stride` field gives its length), so those parse fine; only a few
header dwords and per-object record tails remain undecoded.

## PAK caveats

`pak.ksy` parses the whole structure, with two limits:

1. **PCX RLE.** Texture pixels use PCX run-length encoding, which `process:`
   can't express. `texture.data` is the compressed bytes; decode with
   `rle_decode` in `../src/pak.py`, or a custom Kaitai process routine.
2. **Byte-offset references.** Faces, parts and collision triangles point at
   other records by *byte offset*, not index. The spec adds computed
   `*_index` / `v0`..`v2` instances (offset divided by the record size), but
   Kaitai can't turn those into object references, so look them up in the
   arrays yourself.
