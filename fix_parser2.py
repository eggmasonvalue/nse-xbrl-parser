import re

with open('src/nse_xbrl_parser/parser.py', 'r') as f:
    content = f.read()

fallback_logic = """    if not found_facts:
        raise ValueError("Arelle loaded model but found 0 facts. Schema resolution or validation failed.")

    # Extreme Fallback: NSE schemas often contain un-taxonomized or misspelled items
    # (e.g. 'CategoryOfAllotees', 'PercentageOfTotalIssueSize') that Arelle explicitly
    # drops entirely across all taxonomy versions. We will use a fast raw XML sweep
    # to rescue these fields.
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(final_xbrl_path)
        root = tree.getroot()

        # Track what Arelle successfully pulled so we don't duplicate its work
        arelle_keys = set(parsed_data.keys())
        # Track raw fallback uniqueness via context and label to safely build arrays
        unique_fallback_facts = set()

        for elem in root.iter():
            text = elem.text
            if text and text.strip():
                text = text.strip()
                tag = elem.tag.split("}")[-1]

                # Ignore purely structural/XBRL internal tags
                if tag in ('context', 'entity', 'identifier', 'period', 'instant',
                           'startDate', 'endDate', 'segment', 'explicitMember',
                           'typedMember', 'unit', 'unitDenominator', 'unitNumerator', 'xbrl'):
                    continue

                # Create a human readable label, e.g. "CategoryOfAllotees" -> "Category of allotees"
                # Using regex to insert space before capitals
                human_lbl = re.sub(r"([a-z])([A-Z])", r"\1 \2", tag).capitalize()

                # If Arelle already mapped this property, trust Arelle's validation over our raw sweep
                if human_lbl in arelle_keys:
                    continue

                # We need to distinguish duplicates within the fallback itself (like arrays of CategoryOfAllotees).
                # We can use the element's contextRef attribute.
                ctx_ref = elem.attrib.get("contextRef")
                if ctx_ref:
                    fact_key = (human_lbl, ctx_ref, text)
                    if fact_key in unique_fallback_facts:
                        continue
                    unique_fallback_facts.add(fact_key)

                if human_lbl not in parsed_data:
                    parsed_data[human_lbl] = text
                else:
                    existing = parsed_data[human_lbl]
                    if isinstance(existing, list):
                        existing.append(text)
                    else:
                        parsed_data[human_lbl] = [existing, text]
    except Exception as e:
        logger.debug(f"Raw XML fallback extraction failed: {e}")

    return parsed_data"""

new_content = re.sub(
    r'    if not found_facts:\n        raise ValueError\("Arelle loaded model but found 0 facts\. Schema resolution or validation failed\."\)\n\n    return parsed_data',
    fallback_logic,
    content,
    flags=re.DOTALL
)

with open('src/nse_xbrl_parser/parser.py', 'w') as f:
    f.write(new_content)
