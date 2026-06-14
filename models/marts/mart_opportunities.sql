{{ config(materialized='table') }}

WITH opps AS (

    SELECT * FROM {{ ref('stg_sam_opportunities') }}

),

naics AS (

    SELECT * FROM {{ ref('target_naics') }}

),

joined AS (

    SELECT
        o.*,
        n.description AS naics_description,
        n.priority    AS naics_priority
    FROM opps o
    LEFT JOIN naics n
        ON o.naics_code = n.naics_code

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
        archive_date,
        days_since_posted,
        days_until_deadline,
        deadline_urgency,

        -- Classification
        naics_code,
        naics_description,
        naics_priority,
        psc_code,
        notice_type,
        base_notice_type,
        bid_lifecycle_stage,

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

    FROM categorized

)

SELECT * FROM final