import { Router } from "express";
import { anthropic } from "@workspace/integrations-anthropic-ai";

const router = Router();

const SYSTEM_PROMPT = `You are an environmental data extractor for a cannabis cultivation facility. Extract structured data from images of monitoring screens or handwritten log sheets.

CRITICAL FILTER RULE: Only extract data for FLOWER rooms. Skip and ignore any row or room labeled veg, vegetation, clone, clones, mother, mom, or any non-flower designation. Do not include those rows in the output at all.

ZONE MAPPING — Flower rooms only (Zone Designation → Room ID):
Flower 1 = EF1, Flower 2 = EF2, Flower 3 = EF3, Flower 4 = EF4, Flower 5 = EF5, Flower 6 = EF6, Flower 7 = EF7, Flower 8 = EF8
AB Flower 1 = AB1, AB Flower 2 = AB2, AB Flower 3 = AB3, AB Flower 4 = AB4, AB Flower 5 = AB5, AB Flower 6 = AB6, AB Flower 7 = AB7, AB Flower 8 = AB8
GH Flower 1 = GH1, GH Flower 2 = GH2, GH Flower 3 = GH3, GH Flower 4 = GH4, GH Flower 5 = GH5, GH Flower 6 = GH6, GH Flower 7 = GH7, GH Flower 8 = GH8

SOURCE TYPE 1 — TrolMaster HCS-1 screen:
Single room at a time. Extract: Temp (°F), Humidity (%), CO2 (ppm). Date/time stamp at top. Room ID must be provided by user context.

SOURCE TYPE 2 — Zone Overview screen (Infinium/Anderson table):
Columns: Zone Designation | Channel A | Channel B | Temperature | Humidity | CO2. Map zone names to Room IDs using lookup above. Extract temp, hum, CO2 per row. Skip rows with 0.0° / 0.0% readings. SKIP any row that is not a Flower room (veg, clone, mother, mom, etc).

SOURCE TYPE 3 — Handwritten log sheet:
Room ID is at top left. Rows are dates. Target the MOST RECENT date row. Extract: Temp, Hum, CO2. Runoff columns IN/S1/S2/S3 — each has pH (top number) and EC (bottom number) in the same cell. Circled numbers or zeros = N/A.

ENVIRONMENTAL OUTPUT FORMAT for Zone Overview (group by building — AB, EF, GH):
[Building] Building
- [RoomID] ([Zone Designation]) — [Temp]° // [Hum]% // [CO2] ppm

Example: - EF1 (Flower 1) — 70° // 67.5% // 1030 ppm

Round temp to nearest whole number. CO2 to nearest whole number. Include "ppm" after CO2 value.

ENVIRONMENTAL OUTPUT FORMAT for TrolMaster / Handwritten (group by building):
[Building] Building
- [RoomID] — [Temp]° // [Hum]% // [CO2] ppm

RUNOFF OUTPUT FORMAT:
Room | D[XX] | IN: [pH/EC] // S1: [pH/EC] // S2: [pH/EC] // S3: [pH/EC] // Temp: X° // Hum: X% // CO2: XXXX ppm

FLAG RULES — append ⚠️ after the specific reading:
- pH ≤ 5.6, any EC → flag
- pH ≥ 6.3, any EC → flag
- pH ≥ 6.1 AND EC ≥ 3.5 → combo flag
- pH ≤ 5.6 AND EC ≤ 2.8 → combo flag

If a value is ambiguous or illegible, use [?] and do not guess.

Return ONLY the formatted output. No preamble, no explanation.`;

router.post("/extract", async (req, res) => {
  try {
    const { images, roomOverride } = req.body as {
      images: Array<{ base64: string; mediaType: string }>;
      roomOverride?: string;
      building?: "AB" | "EF" | "GH";
    };

    if (!images || !Array.isArray(images) || images.length === 0) {
      res.status(400).json({ error: "No images provided" });
      return;
    }

    const contextNote = roomOverride?.trim()
      ? `User context: This image is from room ${roomOverride.trim().toUpperCase()}. Use this as the Room ID.`
      : "Map zone names using the lookup table. If room ID cannot be determined, use [?].";

    const content: Anthropic.MessageParam["content"] = [
      ...images.map(
        (img): Anthropic.ImageBlockParam => ({
          type: "image",
          source: {
            type: "base64",
            media_type: img.mediaType as
              | "image/jpeg"
              | "image/png"
              | "image/gif"
              | "image/webp",
            data: img.base64,
          },
        }),
      ),
      {
        type: "text",
        text:
          contextNote +
          "\n\nExtract all environmental data from these images.",
      },
    ];

    const message = await anthropic.messages.create({
      model: "claude-sonnet-4-6",
      max_tokens: 8192,
      system: SYSTEM_PROMPT,
      messages: [{ role: "user", content }],
    });

    const text = message.content
      .map((b) => (b.type === "text" ? b.text : ""))
      .join("");

    const selectedBuilding = req.body.building;
    const cleaned = text
      .split("\n")
      .filter((line) => {
        const trimmed = line.trim();
        return trimmed && !/^(AB|EF|GH)\s+Building$/i.test(trimmed);
      })
      .join("\n")
      .trim();

    const prefix = selectedBuilding ? `${selectedBuilding} Building\n` : "";
    res.json({ result: `${prefix}${cleaned}` });
  } catch (err) {
    req.log.error({ err }, "Extraction failed");
    const message = err instanceof Error ? err.message : "Unknown error";
    res.status(500).json({ error: message });
  }
});

export default router;
