import { addCollection, type IconifyJSON } from '@iconify/vue/offline'
import collections from '@/assets/generated/iconify-bundle.json'

// The offline Iconify entry point has no network loader. Every icon used by
// the admin source and backend module catalog is generated into this bundle
// before production builds, so restrictive CSP and isolated networks remain
// fully functional.
for (const collection of collections) {
  addCollection(collection as IconifyJSON)
}
