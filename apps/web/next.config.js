const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@finreg/core"],
  poweredByHeader: false,
  images: {
    // Disable built-in optimization endpoint to reduce exposure to image optimizer DoS vectors.
    unoptimized: true
  }
};

module.exports = nextConfig;
