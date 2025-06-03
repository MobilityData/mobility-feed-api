let previewBaseUrl = '';
try {
  const previewUrlBase64 = process.env.LHCI_PREVIEW_URL_BASE64;
  if (previewUrlBase64) {
    const decodedUrl = Buffer.from(previewUrlBase64, 'base64').toString('utf-8');
    console.log("Decoded preview URL:", decodedUrl);
    previewBaseUrl = decodedUrl;
  } else {
    console.error("LHCI_PREVIEW_URL_BASE64 environment variable is not set.");
  }
} catch (error) {
  console.error("Error decoding LHCI_PREVIEW_URL_BASE64:", error);
}

console.log("environemtnt variable LHCI_PREVIEW_URL:", previewUrlBase64);

module.exports = {
  ci: {
    collect: {
      url: [
        `${previewBaseUrl}/`,
        `${previewBaseUrl}/feeds`,
        `${previewBaseUrl}/feeds/gtfs/mdb-2126`,
        `${previewBaseUrl}/feeds/gtfs_rt/mdb-2585`,
        `${previewBaseUrl}/gbfs/gbfs-flamingo_porirua`
      ],
      numberOfRuns: 1, // 1 to speed up the CI process but can be increased for more reliable results
      settings: {
        formFactor: 'desktop',
        throttlingMethod: 'provided',
        skipAudits: ['robots-txt', 'is-crawlable'],
        screenEmulation: {
          mobile: false,
          width: 1350,
          height: 940,
          deviceScaleRatio: 1,
          disabled: false
        }
      }
    },
    upload: {
      target: 'temporary-public-storage'
    }
  }
};