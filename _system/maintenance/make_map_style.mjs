// Makes map-style-light.json, the offline map's style (maintainers only; the kit ships the result).
//   npm i @protomaps/basemaps@5.7.2 && node make_map_style.mjs > map-style-light.json
// GLYPHS / SPRITE / PMTILES are filled in on the drive by offline_map.install_assets().
import { layers, namedFlavor } from "@protomaps/basemaps";
const style = {
  version: 8,
  glyphs: "GLYPHS/{fontstack}/{range}.pbf",
  sprite: "SPRITE",
  sources: { protomaps: { type: "vector", url: "PMTILES", attribution: "© OpenStreetMap contributors, Protomaps" } },
  layers: layers("protomaps", namedFlavor("light"), { lang: "en" }),
};
process.stdout.write(JSON.stringify(style));
