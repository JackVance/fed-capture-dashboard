{{ config(materialized='table') }}

WITH psc AS (

    SELECT * FROM {{ ref('psc_codes') }}

),

enriched AS (

    SELECT
        psc_code,
        psc_name,

        -- Service vs Product based on code shape
        -- Alpha-prefix codes are services; numeric codes are products
        CASE
            WHEN LEFT(psc_code, 1) BETWEEN 'A' AND 'Z' THEN 'Service'
            WHEN LEFT(psc_code, 1) BETWEEN '0' AND '9' THEN 'Product'
            ELSE 'Other'
        END AS psc_type,

        -- High-level category from first character (FY federal supply group)
        CASE SUBSTR(psc_code, 1, 1)
            WHEN 'A' THEN 'R&D'
            WHEN 'B' THEN 'Special Studies & Analysis'
            WHEN 'C' THEN 'Architecture & Engineering'
            WHEN 'D' THEN 'IT Services'
            WHEN 'E' THEN 'Purchase of Structures & Facilities'
            WHEN 'F' THEN 'Natural Resources & Conservation'
            WHEN 'G' THEN 'Social Services'
            WHEN 'H' THEN 'Quality Control & Inspection'
            WHEN 'J' THEN 'Maintenance & Repair'
            WHEN 'K' THEN 'Modification of Equipment'
            WHEN 'L' THEN 'Technical Representation'
            WHEN 'M' THEN 'Operation of Government Facilities'
            WHEN 'N' THEN 'Installation of Equipment'
            WHEN 'P' THEN 'Salvage Services'
            WHEN 'Q' THEN 'Medical Services'
            WHEN 'R' THEN 'Support Services'
            WHEN 'S' THEN 'Utilities & Housekeeping'
            WHEN 'T' THEN 'Photographic, Mapping, Printing'
            WHEN 'U' THEN 'Education & Training'
            WHEN 'V' THEN 'Transportation, Travel, Relocation'
            WHEN 'W' THEN 'Lease/Rental of Equipment'
            WHEN 'X' THEN 'Lease/Rental of Facilities'
            WHEN 'Y' THEN 'Construction of Structures'
            WHEN 'Z' THEN 'Maintenance of Structures'
            ELSE 'Products'  -- Numeric codes
        END AS psc_category,

        SUBSTR(psc_code, 1, 1) AS psc_category_prefix,

        -- Parent code (everything but last char) for hierarchical rollup
        CASE
            WHEN LENGTH(psc_code) > 1 THEN SUBSTR(psc_code, 1, LENGTH(psc_code) - 1)
            ELSE NULL
        END AS parent_psc_code

    FROM psc

)

SELECT * FROM enriched