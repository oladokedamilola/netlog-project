# NetLog – Network Log Analyzer (SaaS)

NetLog is a lightweight SaaS platform that helps users quickly analyze network log files such as Apache, Nginx, and IIS. It transforms raw log data into meaningful insights, charts, and downloadable reports — all with no configuration or setup required.

---

## ✨ Features

### Core Features
- Upload and analyze network log files (Apache, Nginx, IIS)
- Automatic parsing and extraction of key metrics
- Visualization of network activity with interactive charts
- Insights such as:
  - Top IP sources and destinations
  - Most common protocols and status codes
  - Traffic spikes and error patterns
- Filtering and sorting of processed log data
- Downloadable analysis reports

### Planned Enhancements
- Smart insights (e.g., error rate trends, traffic anomalies)
- Security-focused metrics:
  - Suspicious IP detection
  - Repeated failed access attempts
  - Potential SQL injection pattern detection
- IP reputation lookup using external APIs
- Advanced charting and multi-log comparison
- Saved analysis history per user

### Future Features
- Email summary reports (daily/weekly)
- Real-time streaming log analytics
- Multi-tenant SaaS support
- Subscription/billing model
- Machine learning–based anomaly detection

---

## 🚀 How It Works

1. **Select the log type**  
   Users begin by choosing the type of log file they want to analyze (Apache, Nginx, IIS, etc.).

2. **Upload the log file**  
   The system processes the file using the appropriate parser.

3. **View the analysis dashboard**  
   After processing, users can explore:
   - Parsed data  
   - Interactive charts  
   - Metrics and insights  
   - Filtering and searching tools  

4. **Download the report**  
   Users can export the generated analysis report for offline use or sharing.

---

## 🛠️ Tech Stack (Core)

**Backend:**  
- Django (Python)

**Frontend:**  
- HTML5  
- CSS3  
- Bootstrap 5  
- JavaScript

**Database:**  
- SQLite (development)

---
