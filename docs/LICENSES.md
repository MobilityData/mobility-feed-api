# Feed Licenses

This page explains how license information is managed and automatically matched to public transit data feeds within the **Mobility Feed API**.
It also describes where the license data comes from and how the system determines which license applies to a given feed.


## Where the License Information Comes From

License details are sourced from the [**Licenses-AAS**](https://github.com/MobilityData/licenses-aas) project, an open repository that organizes licenses according to:

* **Permissions** – what users are allowed to do (for example, modify or share the data)
* **Conditions** – what users must do (for example, give credit to the author)
* **Limitations** – what users cannot do (for example, claim warranty or hold authors liable)

Each license in that repository includes its official SPDX identifier, name, and a link to the full text of the license.


## How License Matching Works

When a feed includes a **license URL**, the system tries to recognize and link it to a known open-data license.
This process ensures that each feed clearly indicates how its data can be used and shared.

The matching process follows several steps:

1. **Exact Match**
   The system checks if the feed’s license URL exactly matches one from the license catalog.
   This is the most reliable form of matching.

2. **Close or “Fuzzy” Match**
   If no exact match is found, the system looks for similar URLs that differ only slightly (for example, extra slashes or query parameters).

3. **Domain Match**
   Some organizations host multiple licenses under the same domain.
   If the URL points to such a domain, the system checks all known licenses from that source.

4. **Text or Content Match**
   As a last resort, if the link leads to a page containing license text, the system analyzes the content and compares it to known license texts.


## Regional or Localized Licenses

If a license URL points to a **localized version** (for example, a country-specific version of a Creative Commons license),
the system identifies the corresponding **standard SPDX license** and adds a note explaining the regional variant.


## Understanding the Matching Results

Each match includes:

* **License name and ID** – e.g., *MIT License (MIT)*
* **Match type** – how the license was identified (exact, fuzzy, domain, or content)
* **Confidence level** – how certain the system is about the match (higher = stronger match)
* **Notes** – any additional details, such as localized versions or domain inference


## License Rules

Some licenses in the catalog include detailed **rules** that describe what users *can*, *must*, and *cannot* do under that license.
However, not all licenses currently have these rules defined.

These rules are maintained in the [**Licenses-AAS**](https://github.com/MobilityData/licenses-aas) repository.
If you notice a license missing its rules, you’re encouraged to contribute by adding them, helping improve clarity and consistency for all users of open data.


## Keeping License Data Accurate

The Licenses-AAS project is regularly updated to include new and revised open-data licenses.
This ensures that the Mobility Feed API always reflects the most current and reliable licensing information.
