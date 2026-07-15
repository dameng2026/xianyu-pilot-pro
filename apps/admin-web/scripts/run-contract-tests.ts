const contractTests = [
  './admin-access-boundary-contract.test',
  './http-error-contract.test',
  './notification-config-state-contract.test',
  './admin-truthful-state-contract.test',
  './inactive-feature-truthfulness-contract.test',
  './content-config-contract.test',
  './content-config-request-contract.test',
  './dashboard-overview-contract.test',
  './enterprise-safety-contract.test',
  './release-metadata-contract.test'
]

for (const contractTest of contractTests) {
  await import(contractTest)
}

console.log(`admin-contract-tests: ${contractTests.length} suites ok`)
