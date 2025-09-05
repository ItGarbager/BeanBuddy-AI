const { configureRuntimeEnv } = require('next-runtime-env/build/configure');

const nextConfig = {
  env: {
    ...configureRuntimeEnv(),
  },
  output: 'standalone',
  typescript: {
    // !! WARN !!
    // Dangerously allow production builds to successfully complete even if
    // your project has type errors.
    // !! WARN !!
    ignoreBuildErrors: true,
  },
  experimental: {
    serverActions: {
      bodySizeLimit: "5mb",
    },
  },
  webpack(config, { isServer, dev }) {
    config.experiments = {
      asyncWebAssembly: true,
      layers: true,
    };

    return config;
  },
  async redirects() {
    return [
    ]
  },
};

module.exports = nextConfig;
