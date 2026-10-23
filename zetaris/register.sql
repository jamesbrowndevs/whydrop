CREATE LIGHTNING DATABASE WHYDROP_FILES DESCRIBE BY "WhyDrop files" OPTIONS ();
CREATE LIGHTNING FILESTORE TABLE orders FROM WHYDROP_FILES FORMAT csv OPTIONS (path "/home/zetaris/customer-data/shared/whydrop/orders", header "true", inferSchema "true");
CREATE LIGHTNING FILESTORE TABLE products FROM WHYDROP_FILES FORMAT csv OPTIONS (path "/home/zetaris/customer-data/shared/whydrop/products", header "true", inferSchema "true");
CREATE LIGHTNING FILESTORE TABLE marketing_spend FROM WHYDROP_FILES FORMAT csv OPTIONS (path "/home/zetaris/customer-data/shared/whydrop/marketing_spend", header "true", inferSchema "true");
CREATE LIGHTNING FILESTORE TABLE web_traffic FROM WHYDROP_FILES FORMAT json OPTIONS (path "/home/zetaris/customer-data/shared/whydrop/web_traffic", multiLine "true");
CREATE LIGHTNING FILESTORE TABLE pricing_changes FROM WHYDROP_FILES FORMAT json OPTIONS (path "/home/zetaris/customer-data/shared/whydrop/pricing_changes", multiLine "true");
CREATE LIGHTNING FILESTORE TABLE release_log FROM WHYDROP_FILES FORMAT json OPTIONS (path "/home/zetaris/customer-data/shared/whydrop/release_log", multiLine "true");
CREATE DATASOURCE WHYDROP_PG DESCRIBE BY "WhyDrop Postgres support DB" OPTIONS (jdbcdriver "org.postgresql.Driver", jdbcurl "jdbc:postgresql://postgres:5432/whydrop_ops", username "@PGUSER@", password "@PGPASS@");
REGISTER DATASOURCE TABLES FROM WHYDROP_PG;
