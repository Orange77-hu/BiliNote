import request from '@/utils/request' // 你项目里封装好的axios或者fetch

export const uploadFile = (formData: FormData) => {
  return request.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    // 大视频（500MB+）局域网上传常超过全局 10s 超时，会被 axios 掐断并弹
    // 「请求失败，请检查网络连接或稍后再试」——上传取消超时限制。
    timeout: 0,
  })
}
