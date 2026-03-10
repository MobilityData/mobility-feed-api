-- create location continent table which has fk reference to location table country code
CREATE TABLE LOCATION_CONTINENT (
    continent VARCHAR(255),
    country_code VARCHAR(3) PRIMARY KEY,
    CONSTRAINT loc_cont_fk
        FOREIGN KEY(country_code)
        REFERENCES LOCATION(country_code)
);

-- remove the previously created location_view
DROP VIEW IF EXISTS LOCATION_VIEW;