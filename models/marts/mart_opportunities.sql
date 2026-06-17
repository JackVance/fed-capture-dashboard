{{ config(materialized='table') }}

WITH opps AS (

    SELECT * FROM {{ ref('stg_sam_opportunities') }}

),

joined AS (

    SELECT
        o.*,
        n.naics_title       AS naics_description,
        n.sector_code,
        n.sector_name,
        p.psc_name,
        p.psc_category,
        p.psc_type
    FROM opps o
    LEFT JOIN {{ ref('dim_naics') }} n
        ON o.naics_code = n.naics_code
    LEFT JOIN {{ ref('dim_psc') }} p
        ON o.psc_code = p.psc_code

),

categorized AS (

    SELECT
        joined.*,

        -- Date derivations
        DATEDIFF('day', posted_date, CURRENT_DATE())                      AS days_since_posted,
        IFF(response_deadline > CURRENT_TIMESTAMP(),
            DATEDIFF('day', CURRENT_TIMESTAMP(), response_deadline),
            NULL)                                                          AS days_until_deadline,

        -- Deadline urgency for filtering
        CASE
            WHEN response_deadline IS NULL                                       THEN 'No Deadline'
            WHEN response_deadline < CURRENT_TIMESTAMP()                         THEN 'Expired'
            WHEN DATEDIFF('day', CURRENT_TIMESTAMP(), response_deadline) <= 7    THEN 'Closes This Week'
            WHEN DATEDIFF('day', CURRENT_TIMESTAMP(), response_deadline) <= 30   THEN 'Closes This Month'
            ELSE                                                                      'Open > 30 Days'
        END                                                                AS deadline_urgency,

        -- Lifecycle stage rolled up from notice_type
        CASE
            WHEN notice_type IN ('Sources Sought', 'Special Notice', 'Presolicitation', 'Intent to Bundle Requirements (DoD-Funded)')
                THEN 'Pre-Bid'
            WHEN notice_type IN ('Solicitation', 'Combined Synopsis/Solicitation')
                THEN 'Bid Window'
            WHEN notice_type IN ('Award Notice', 'Justification', 'Justification and Approval (J&A)', 'Fair Opportunity / Limited Sources Justification')
                THEN 'Post-Award'
            ELSE 'Other'
        END                                                                AS bid_lifecycle_stage,

        -- Set-aside qualification category
        CASE
            WHEN type_of_set_aside IS NULL OR type_of_set_aside ILIKE '%no set%aside%'   THEN 'Open Competition'
            WHEN type_of_set_aside ILIKE '%8(a)%'                                         THEN '8(a) Business Development'
            WHEN type_of_set_aside ILIKE '%hubzone%'                                      THEN 'HUBZone'
            WHEN type_of_set_aside ILIKE '%women%owned%'                                  THEN 'Women-Owned Small Business'
            WHEN type_of_set_aside ILIKE '%service-disabled%veteran%'                     THEN 'SDVOSB'
            WHEN type_of_set_aside ILIKE '%veteran%'                                      THEN 'Veteran-Owned Small Business'
            WHEN type_of_set_aside ILIKE '%indian%'                                       THEN 'Indian-Owned (ISBEE)'
            WHEN type_of_set_aside ILIKE '%small business%'                               THEN 'Small Business (General)'
            ELSE 'Other Restricted'
        END                                                                AS set_aside_category,

        -- Agency hierarchy split from the dot-delimited path
        SPLIT_PART(agency_path, '.', 1)                                    AS department,
        SPLIT_PART(agency_path, '.', 2)                                    AS agency,
        SPLIT_PART(agency_path, '.', 3)                                    AS command,
        SPLIT_PART(agency_path, '.', 4)                                    AS office

    FROM joined

),

flagged AS (

    SELECT
        categorized.*,

        -- Atomic work-path flags based on NAICS and PSC categorization
        (psc_category = 'IT Services'
            OR naics_code IN ('511210', '518210', '541511', '541512', '541513', '541519'))
            AS is_software_or_it,

        -- Studies and accessible analytical work
        (psc_category = 'Special Studies & Analysis'
            OR naics_code IN ('541910'))
            AS is_studies_or_analysis,

        -- Specialized R&D with typical PhD/lab requirements
        (psc_category = 'R&D'
            OR naics_code IN ('541713', '541714', '541715', '541720'))
            AS is_specialized_research,

        (psc_category = 'Architecture & Engineering'
            OR LEFT(naics_code, 4) = '5413')
            AS is_engineering_services,

        (LEFT(naics_code, 4) = '5416')
            AS is_consulting_advisory,

        (psc_category IN (
            'Construction of Structures',
            'Maintenance of Structures',
            'Maintenance & Repair',
            'Modification of Equipment'
         )
            OR LEFT(naics_code, 2) = '23')
            AS is_construction_or_maintenance,

        (psc_category IN (
            'Operation of Government Facilities',
            'Installation of Equipment',
            'Utilities & Housekeeping',
            'Transportation, Travel, Relocation',
            'Lease/Rental of Equipment',
            'Lease/Rental of Facilities'
         ))
            AS is_physical_service,

        (psc_type = 'Product')
            AS is_product_procurement

    FROM categorized

),

flagged_composite AS (

    SELECT
        flagged.*,

        -- Composite umbrella flags
        (is_software_or_it
         OR is_studies_or_analysis
         OR is_specialized_research
         OR is_engineering_services
         OR is_consulting_advisory)
            AS is_intellectual_product,

        -- Personal target zone: intellectual product, excluding hands-on/physical work, credentialed engineering services, specialized research
        ((is_software_or_it
            OR is_studies_or_analysis
            OR is_consulting_advisory)
            AND NOT is_construction_or_maintenance
            AND NOT is_physical_service
            AND NOT is_product_procurement
            AND NOT is_engineering_services
            AND NOT is_specialized_research)
                AS is_personal_target_zone,

        -- Primary work path (mutually exclusive, precedence-based)
        CASE
            WHEN is_software_or_it             THEN 'Software & IT'
            WHEN is_studies_or_analysis        THEN 'Studies & Analysis'
            WHEN is_specialized_research       THEN 'Specialized R&D'
            WHEN is_engineering_services       THEN 'Engineering Services'
            WHEN is_consulting_advisory        THEN 'Consulting & Advisory'
            WHEN is_construction_or_maintenance THEN 'Construction & Maintenance'
            WHEN is_physical_service           THEN 'Physical Services'
            WHEN is_product_procurement        THEN 'Product Procurement'
            ELSE 'Other / Uncategorized'
        END AS work_path_primary

    FROM flagged

),

final AS (

    SELECT
        -- Identifiers
        notice_id,
        solicitation_number,

        -- Source links
        ui_link,
        description_url,

        -- Dates
        posted_date,
        response_deadline,
        response_deadline::DATE AS response_deadline_date,
        archive_date,
        days_since_posted,
        days_until_deadline,
        deadline_urgency,

        -- Classification
        naics_code,
        naics_description,
        sector_code,
        sector_name,
        psc_code,
        psc_name,
        -- Derive PSC category from code prefix; resilient to dim coverage gaps
        COALESCE(
            psc_category,
            CASE 
                WHEN psc_code IS NULL THEN 'No PSC Code'
                ELSE 
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
                        ELSE 'Products'
                    END
            END
        ) AS psc_category,
        COALESCE(psc_type,
            CASE 
                WHEN psc_code IS NULL THEN 'No PSC Code'
                WHEN LEFT(psc_code, 1) BETWEEN 'A' AND 'Z' THEN 'Service'
                WHEN LEFT(psc_code, 1) BETWEEN '0' AND '9' THEN 'Product'
                ELSE 'Other'
            END
        ) AS psc_type,
        notice_type,
        base_notice_type,
        bid_lifecycle_stage,

        -- Work path classification flags
        is_software_or_it,
        is_studies_or_analysis,
        is_specialized_research,
        is_engineering_services,
        is_consulting_advisory,
        is_construction_or_maintenance,
        is_physical_service,
        is_product_procurement,
        is_intellectual_product,
        is_personal_target_zone,
        work_path_primary,

        -- Status & qualification
        is_active,
        type_of_set_aside,
        set_aside_category,
        (is_active
         AND bid_lifecycle_stage = 'Bid Window'
         AND response_deadline > CURRENT_TIMESTAMP())                      AS is_bid_ready,

        -- Display
        title,
        agency_path,
        department,
        agency,
        command,
        office,

        -- Location
        state,
        country_code,
        zip_code,
        is_us_location,

        -- Attachments
        has_attachments,

        -- Metadata
        ingested_at

    FROM flagged_composite

)

SELECT * FROM final