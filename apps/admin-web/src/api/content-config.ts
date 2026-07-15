export function buildFreshContentListRequest(url: string) {
  return {
    url,
    cacheTtl: 0,
    skipDedupe: true,
  }
}
