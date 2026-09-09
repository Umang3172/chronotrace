/** @type {import('next').NextConfig} */
// `output: 'export'` emits a fully static site into ui/out — no Node server, so the
// dashboard can sit on S3, CloudFront or Amplify and cannot stall on a request during
// a demo. Every route is already static or SSG, so nothing is given up by doing this:
// incidents are read from a file at build time, and `generateStaticParams` enumerates
// them. `images.unoptimized` is required because the default image loader needs a
// server; the dashboard ships no raster images, so it costs nothing.
const nextConfig = {
  reactStrictMode: true,
  output: 'export',
  images: { unoptimized: true },
  trailingSlash: true,
};
export default nextConfig;
