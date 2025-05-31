const withSvgr = require('next-plugin-svgr');

module.exports = withSvgr({
  reactStrictMode: true,
  webpack(config, options) {
    return config;
  },
});