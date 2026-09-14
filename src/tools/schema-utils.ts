/**
 * Shared zod helpers for MCP tool input schemas.
 */

import { z } from 'zod';

/**
 * A string field that also accepts a number.
 *
 * Article numbers ("105", "5.35") and region codes ("77") are strings in the
 * database and in our JSON schemas, but many MCP clients - the official
 * inspector CLI among them - coerce a bare `105` on the wire into the JSON
 * number `105`. Rejecting that would be a hard failure over a spelling
 * difference, and converting a number to its decimal string is lossless and
 * unambiguous for these identifiers, so accept both and normalise to string.
 *
 * This is deliberately NOT applied to `eo_number`, where leading zeros are
 * significant and a number would lose them.
 */
export function numericString(description: string) {
  return z
    .union([z.string(), z.number()])
    .transform((value) => (typeof value === 'number' ? String(value) : value))
    .describe(description);
}
