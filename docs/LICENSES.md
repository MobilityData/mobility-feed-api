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

2. **Creative Commons Resolver**
If no exact match is found, the system checks whether the URL represents a Creative Commons license
(including international and regional variants such as JP, FR, DE).
When detected, the resolver maps the URL to the correct SPDX ID and adds notes about regional versions if applicable.

3. **Generic Heuristics**
If the URL follows a recognizable pattern (e.g., apache.org/licenses/LICENSE-2.0),
the system applies rule-based heuristics to infer the likely SPDX ID.

4. **Fuzzy Match (same host only)**
If no deterministic match is found, the system compares the URL against known license URLs from the same domain
using string-similarity scoring.
This step captures minor variations such as trailing slashes, redirects, or small path differences.

## Regional or Localized Licenses

If a license URL points to a **localized version** (for example, a country-specific version of a Creative Commons license),
the system identifies the corresponding **standard SPDX license** and adds a note explaining the regional variant.


## Understanding the Matching Results

Each match includes:

* **License name and ID** – e.g., *MIT License (MIT)*
* **Match type** – how the license was identified (exact, fuzzy, or heuristic)
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
