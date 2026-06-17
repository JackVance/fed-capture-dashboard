{{ config(materialized='table') }}

WITH naics AS (

    SELECT * FROM {{ ref('naics_codes') }}

),

sectors AS (

    SELECT '11' AS sector_code, 'Agriculture, Forestry, Fishing and Hunting' AS sector_name UNION ALL
    SELECT '21', 'Mining, Quarrying, and Oil and Gas Extraction' UNION ALL
    SELECT '22', 'Utilities' UNION ALL
    SELECT '23', 'Construction' UNION ALL
    SELECT '31', 'Manufacturing' UNION ALL
    SELECT '32', 'Manufacturing' UNION ALL
    SELECT '33', 'Manufacturing' UNION ALL
    SELECT '42', 'Wholesale Trade' UNION ALL
    SELECT '44', 'Retail Trade' UNION ALL
    SELECT '45', 'Retail Trade' UNION ALL
    SELECT '48', 'Transportation and Warehousing' UNION ALL
    SELECT '49', 'Transportation and Warehousing' UNION ALL
    SELECT '51', 'Information' UNION ALL
    SELECT '52', 'Finance and Insurance' UNION ALL
    SELECT '53', 'Real Estate and Rental and Leasing' UNION ALL
    SELECT '54', 'Professional, Scientific, and Technical Services' UNION ALL
    SELECT '55', 'Management of Companies and Enterprises' UNION ALL
    SELECT '56', 'Administrative and Support and Waste Management and Remediation Services' UNION ALL
    SELECT '61', 'Educational Services' UNION ALL
    SELECT '62', 'Health Care and Social Assistance' UNION ALL
    SELECT '71', 'Arts, Entertainment, and Recreation' UNION ALL
    SELECT '72', 'Accommodation and Food Services' UNION ALL
    SELECT '81', 'Other Services (except Public Administration)' UNION ALL
    SELECT '92', 'Public Administration'

),

final AS (

    SELECT
        n.naics_code,
        n.naics_title,
        SUBSTR(n.naics_code, 1, 2)  AS sector_code,
        s.sector_name,
        SUBSTR(n.naics_code, 1, 3)  AS subsector_code,
        SUBSTR(n.naics_code, 1, 4)  AS industry_group_code,
        SUBSTR(n.naics_code, 1, 5)  AS naics_industry_code
    FROM naics n
    LEFT JOIN sectors s
        ON SUBSTR(n.naics_code, 1, 2) = s.sector_code

)

SELECT * FROM final