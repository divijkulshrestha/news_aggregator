from pyspark.sql import SparkSession

print("Hello World")

spark = SparkSession.builder.appName("VersionCheck").getOrCreate()
print(spark.version)

# Create a simple DataFrame
data = [("Alice", 25), ("Bob", 30), ("Charlie", 35)]
columns = ["Name", "Age"]
df = spark.createDataFrame(data, columns)

# Show the DataFrame
df.show()

# Stop the session
spark.stop()
