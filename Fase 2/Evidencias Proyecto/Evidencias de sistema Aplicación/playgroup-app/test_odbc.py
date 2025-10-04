import pyodbc

# Ajusta estos valores según tu entorno
SERVER   = r"TARRO-RGB,1433"            # o r"localhost\SQLEXPRESS"
DATABASE = "PlaygroupPiececitas"   # o el nombre exacto que viste en SSMS
DRIVER   = "ODBC Driver 18 for SQL Server"  # o "ODBC Driver 17 for SQL Server"

conn_str = f"DRIVER={{{DRIVER}}};SERVER={SERVER};DATABASE={DATABASE};Trusted_Connection=Yes;Encrypt=Yes;TrustServerCertificate=Yes"

print("Usando conexión ODBC:", conn_str)
print("Drivers instalados:", pyodbc.drivers())

cn = pyodbc.connect(conn_str)
cur = cn.cursor()
cur.execute("SELECT TOP 1 ActivityId, Name, Area FROM pg.ActivityCatalog ORDER BY ActivityId")
row = cur.fetchone()
print("OK ->", row)
cn.close()
