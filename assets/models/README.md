# 3D models of today's cars

Third-party models, **CC BY 4.0** (https://creativecommons.org/licenses/by/4.0/), not BMW data. The app shows the
attribution on screen (`bmw_req.car_zones.MODELS_GLTF`).

| File | Model | Author | Source |
|---|---|---|---|
| `f70.glb` | Bmw-1-series 2025 (AI-generated mesh) | teenlin3 | https://sketchfab.com/3d-models/bmw-1-series-2025-aca5bc34dd014aff89eef647124b485d |
| `g60.glb` | i5 | akyolefe319 | https://sketchfab.com/3d-models/i5-1e52b6b8821040c2aea037b7c029a20d |
| `g70.glb` | 2023 BMW I7 G70 | NazhDesign | https://sketchfab.com/3d-models/2023-bmw-i7-g70-07937cca69864dfe9f4b4ed235fc32f7 |

**Changes:** compressed with `gltf-transform optimize --compress meshopt --texture-compress webp --texture-size 2048
--simplify false` (same triangles; 74 MB → 8 MB). The Docker image copies them to `/app/data/models`; locally
`data/models/` (mounted over it) wins if present.
