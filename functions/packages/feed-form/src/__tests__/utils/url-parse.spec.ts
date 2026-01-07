import { isValidZipUrl, isValidZipDownload } from "../../impl/utils/url-parse";
import axios from "axios";

jest.mock("axios");
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe("isValidZipUrl", () => {
  it("returns true for valid .zip URL", () => {
    expect(isValidZipUrl("https://file-examples.com/wp-content/storage/2017/02/zip_2MB.zip")).toBe(true);
    expect(isValidZipUrl("https://file-examples.com/wp-content/storage/2017/02/zip_5MB.zip")).toBe(true);
  });

  it("returns false for non-.zip URL", () => {
    expect(isValidZipUrl("https://file-examples.com/wp-content/storage/2017/02/file_example_CSV_5000.csv")).toBe(false);
    expect(isValidZipUrl("https://file-examples.com/wp-content/storage/2017/02/file_example_JSON_1kb.json")).toBe(false);
  });

  it("returns false for invalid or empty input", () => {
    expect(isValidZipUrl("")).toBe(false);
    expect(isValidZipUrl(undefined)).toBe(false);
    expect(isValidZipUrl(null)).toBe(false);
    expect(isValidZipUrl("not a url")).toBe(false);
  });
});

describe("isValidZipDownload", () => {
  afterEach(() => jest.resetAllMocks());

  it("returns true if content-type includes zip", async () => {
    mockedAxios.head.mockResolvedValueOnce({
      headers: { "content-type": "application/zip" }
    } as any);
    await expect(isValidZipDownload("https://file-examples.com/wp-content/storage/2017/02/zip_2MB.zip")).resolves.toBe(true);
  });

  it("returns true if content-disposition includes zip", async () => {
    mockedAxios.head.mockResolvedValueOnce({
      headers: { "content-disposition": "attachment; filename=foo.zip" }
    } as any);
    await expect(isValidZipDownload("https://file-examples.com/wp-content/storage/2017/02/zip_2MB.zip")).resolves.toBe(true);
  });

  it("returns false if neither header includes zip", async () => {
    mockedAxios.head.mockResolvedValueOnce({
      headers: { "content-type": "text/plain" }
    } as any);
    await expect(isValidZipDownload("https://file-examples.com/wp-content/storage/2017/02/zip_2MB.zip")).resolves.toBe(false);
  });

  it("returns false for invalid/empty url", async () => {
    await expect(isValidZipDownload("")).resolves.toBe(false);
    await expect(isValidZipDownload(undefined)).resolves.toBe(false);
    await expect(isValidZipDownload(null)).resolves.toBe(false);
  });

  it("returns false if axios throws", async () => {
    mockedAxios.head.mockRejectedValueOnce(new Error("Network error"));
    await expect(isValidZipDownload("https://file-examples.com/wp-content/storage/2017/02/zip_2MB.zip")).resolves.toBe(false);
  });
});
