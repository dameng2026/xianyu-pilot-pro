import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const serverPage = fs.readFileSync(
  path.resolve('src/views/safeguard/server/index.vue'),
  'utf8'
)

assert(
  serverPage.includes('服务器管理暂不可用'),
  '服务器管理未接入真实基础设施后端时，必须明确显示不可用状态'
)
assert(
  serverPage.includes('尚未接入真实主机资产、资源监控和控制后端'),
  '不可用状态必须解释缺失的数据源与控制能力'
)
for (const misleadingContent of [
  'Math.random',
  '192.168.1.100',
  '开机</ElButton>',
  '关机</ElButton>',
  '重启</ElButton>'
]) {
  assert(
    !serverPage.includes(misleadingContent),
    `服务器管理页不得保留伪造指标或无效操作：${misleadingContent}`
  )
}

const articleListPage = fs.readFileSync(
  path.resolve('src/views/article/list/index.vue'),
  'utf8'
)

assert(
  articleListPage.includes('文章管理暂不可用'),
  '文章列表未接入真实内容服务时，必须明确显示不可用状态'
)
assert(
  articleListPage.includes('尚未接入真实文章服务'),
  '文章列表不可用状态必须解释真实后端缺失'
)
for (const misleadingContent of [
  "@/mock/temp/articleList",
  'TODO: 替换为真实 API 调用',
  '新增文章</ElButton>',
  '>编辑</ElButton>'
]) {
  assert(
    !articleListPage.includes(misleadingContent),
    `文章列表不得保留样例数据或无效操作：${misleadingContent}`
  )
}

const articlePublishPage = fs.readFileSync(
  path.resolve('src/views/article/publish/index.vue'),
  'utf8'
)

assert(
  articlePublishPage.includes('文章发布暂不可用'),
  '文章发布未接入真实内容服务时，必须明确显示不可用状态'
)
assert(
  articlePublishPage.includes('不会保存、上传或发布任何内容'),
  '文章发布页必须明确说明不可用状态下不会产生写入'
)
for (const misleadingContent of [
  'qiniu.lingchen.kim',
  'TODO: 替换为真实 API 调用',
  '<ElUpload',
  '@click="submit"'
]) {
  assert(
    !articlePublishPage.includes(misleadingContent),
    `文章发布页不得调用样例接口或保留无效写入入口：${misleadingContent}`
  )
}

const articleDetailPage = fs.readFileSync(
  path.resolve('src/views/article/detail/index.vue'),
  'utf8'
)
const articleCommentPage = fs.readFileSync(
  path.resolve('src/views/article/comment/index.vue'),
  'utf8'
)
const commentWidget = fs.readFileSync(
  path.resolve('src/components/business/comment-widget/index.vue'),
  'utf8'
)

assert(articleDetailPage.includes('文章详情暂不可用'))
assert(articleCommentPage.includes('留言管理暂不可用'))
assert(commentWidget.includes('评论功能暂不可用'))
for (const [label, source, forbidden] of [
  ['文章详情', articleDetailPage, ['qiniu.lingchen.kim', 'axios.get']],
  ['留言管理', articleCommentPage, ["@/mock/temp/commentList", 'Math.random']],
  ['评论组件', commentWidget, ["@/mock/temp/commentDetail", 'ElMessage.success']]
] as const) {
  for (const misleadingContent of forbidden) {
    assert(
      !source.includes(misleadingContent),
      `${label}不得调用样例数据或伪报操作成功：${misleadingContent}`
    )
  }
}

console.log('inactive-feature-truthfulness-contract: ok')
