const previewBaseUrl = process.env.LHCI_PREVIEW_URL || 'https://mobility-feeds-dev--pr-1203-nlp6ow3m.web.app';

console.log("environemtnt variable LHCI_PREVIEW_URL:", process.env.LHCI_PREVIEW_URL);

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
      numberOfRuns: 2,
      settings: {
        formFactor: 'desktop',
        throttlingMethod: 'provided',
        skipAudits: ['robots-txt'],
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