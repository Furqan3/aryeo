/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  distDir: 'build', // instead of .next
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**aryeo.com', // allows aryeo.com and subdomains
      },
      {
        protocol: 'https',
        hostname: '**cdn.aryeo.com',
      },
    ],
  },
};

export default nextConfig;
