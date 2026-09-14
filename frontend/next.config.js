/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // This dev machine has ~7GB RAM; the default worker-per-CPU static generation pool
  // (7 workers here) runs the build out of memory. Cap it to keep builds reliable.
  experimental: {
    cpus: 1,
  },
};

module.exports = nextConfig;
