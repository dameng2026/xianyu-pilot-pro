import request from '../utils/request.js'

export function getBillingPlans() {
  return request({ url: '/billing/plans', method: 'get' }).then(res => res?.data)
}
