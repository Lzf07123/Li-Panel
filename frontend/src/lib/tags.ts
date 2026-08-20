export const MAX_TAGS = 8;
export const MAX_TAG_LENGTH = 20;

/** 逗号（中英文）分隔解析标签：去重、去空、截断数量与长度 */
export function parseTags(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(/[,，]/)
        .map((tag) => tag.trim().slice(0, MAX_TAG_LENGTH))
        .filter(Boolean),
    ),
  ).slice(0, MAX_TAGS);
}

export function formatTags(tags: string[]): string {
  return tags.join(", ");
}
