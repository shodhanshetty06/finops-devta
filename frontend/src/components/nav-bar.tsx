// Deprecated: superseded by components/app-shell.tsx (AppSidebar +
// AppTopbar), wired in via app/(app)/layout.tsx. Kept as an empty module
// rather than deleted - this sandbox's FUSE-mounted output directory
// doesn't allow unlinking files created through the Write tool (`rm`/
// `os.remove` both fail with EPERM), only overwriting them. Not imported
// anywhere, so it isn't part of the production bundle.
export {};
