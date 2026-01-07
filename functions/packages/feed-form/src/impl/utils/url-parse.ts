import axios from "axios";

/**
 * Parses the provided URL to check if it is a valid ZIP file URL
 * @param {string | undefined | null } url The direct download URL
 * @return {boolean} Whether the URL is a valid ZIP file URL
 */
export function isValidZipUrl(url: string | undefined | null): boolean {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    return parsed.pathname.toLowerCase().endsWith(".zip");
  } catch {
    return false;
  }
}

/**
 * Checks if URL points to a valid ZIP file by making HEAD request
 * @param {string | undefined | null } url The download URL
 * @return {boolean} Whether the URL downloads a valid ZIP file
 */
export async function isValidZipDownload(
  url: string | undefined | null
): Promise<boolean> {
  try {
    if (!url) return false;
    const response = await axios.head(url, {maxRedirects: 2});
    const contentType = response.headers["content-type"];
    const contentDisposition = response.headers["content-disposition"];

    if (contentType && contentType.includes("zip")) return true;
    if (contentDisposition && contentDisposition.includes("zip")) return true;
    return false;
  } catch {
    return false;
  }
}