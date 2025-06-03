const previewBaseUrl = process.env.LHCI_PREVIEW_URL || '';

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