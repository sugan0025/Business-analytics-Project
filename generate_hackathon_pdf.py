import os
import subprocess
import shutil

ASSETS_DIR = r"C:\Users\sugan\.gemini\antigravity-ide\scratch\Business-analytics-Project\pdf_assets"
HTML_PATH = os.path.join(ASSETS_DIR, "presentation.html")
OUTPUT_PDF = r"C:\Users\sugan\.gemini\antigravity-ide\scratch\Business-analytics-Project\Faculty_Guide_Selection_Hackathon.pdf"
DOWNLOADS_PDF = r"C:\Users\sugan\Downloads\Faculty_Guide_Selection_Hackathon.pdf"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Faculty Guide Selection System - Hackathon Presentation</title>
<style>
  @page {{
    size: A4 portrait;
    margin: 0;
  }}

  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}

  body {{
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    background: #ffffff;
    line-height: 1.45;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-rendering: geometricPrecision;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}

  .page {{
    width: 210mm;
    min-height: 297mm;
    height: 297mm;
    padding: 13mm 16mm;
    position: relative;
    page-break-after: always;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    background: #ffffff;
    overflow: hidden;
  }}

  /* Header Bar */
  .header {{
    border-bottom: 2px solid #f1f5f9;
    padding-bottom: 9px;
    margin-bottom: 12px;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
  }}

  .header-left h1 {{
    font-size: 21px;
    font-weight: 700;
    color: #0f172a;
    letter-spacing: -0.3px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}

  .header-left p {{
    font-size: 11.5px;
    color: #64748b;
    margin-top: 2px;
    font-weight: 500;
  }}

  .live-badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #f5f3ff;
    border: 1px solid #ddd6fe;
    padding: 5px 13px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    color: #673ab7;
    text-decoration: none;
    transition: all 0.2s ease;
  }}

  .live-dot {{
    width: 7px;
    height: 7px;
    background: #10b981;
    border-radius: 50%;
  }}

  /* Section Titles */
  .section-title {{
    font-size: 11.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #673ab7;
    margin-bottom: 7px;
    display: flex;
    align-items: center;
    gap: 6px;
  }}

  /* Summary Box */
  .summary-box {{
    background: linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%);
    border: 1px solid #e9d5ff;
    border-radius: 7px;
    padding: 10px 13px;
    margin-bottom: 12px;
    font-size: 11.5px;
    color: #4c1d95;
    line-height: 1.5;
  }}

  .summary-box b {{
    font-weight: 700;
    color: #581c87;
  }}

  /* Grid Layouts */
  .grid-4 {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    margin-bottom: 12px;
  }}

  .stack-card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 7px;
    padding: 9px 11px;
  }}

  .stack-card .icon {{
    font-size: 15px;
    margin-bottom: 3px;
  }}

  .stack-card h3 {{
    font-size: 11.5px;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 2px;
  }}

  .stack-card p {{
    font-size: 10px;
    color: #64748b;
    line-height: 1.35;
  }}

  /* Codebase Table */
  .table-wrap {{
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 7px;
    overflow: hidden;
    margin-bottom: 12px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.02);
  }}

  table.code-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
    text-align: left;
  }}

  table.code-table th {{
    background: #f1f5f9;
    color: #334155;
    font-weight: 700;
    padding: 7px 11px;
    border-bottom: 1px solid #e2e8f0;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}

  table.code-table td {{
    padding: 7px 11px;
    border-bottom: 1px solid #f1f5f9;
    color: #1e293b;
    vertical-align: middle;
  }}

  table.code-table tr:last-child td {{
    border-bottom: none;
    background: #faf5ff;
    font-weight: 700;
    color: #673ab7;
  }}

  .pill-py {{
    display: inline-block;
    background: #e0f2fe;
    color: #0369a1;
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
    font-family: 'Consolas', 'Courier New', monospace;
  }}

  .pill-fe {{
    display: inline-block;
    background: #fef3c7;
    color: #b45309;
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
    font-family: 'Consolas', 'Courier New', monospace;
  }}

  /* Diagrams */
  .diagram-wrap {{
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 7px;
    padding: 8px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    margin-bottom: 12px;
  }}

  .diagram-wrap img, .diagram-wrap svg {{
    width: 100%;
    display: block;
  }}

  .diagram-caption {{
    font-size: 9.5px;
    color: #64748b;
    font-weight: 500;
    text-align: center;
    margin-top: 5px;
  }}

  /* Feature Checklist */
  .feature-list {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 9px;
  }}

  .feature-item {{
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-left: 3px solid #673ab7;
    border-radius: 6px;
    padding: 8px 10px;
  }}

  .feature-item h4 {{
    font-size: 10.5px;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 2px;
  }}

  .feature-item p {{
    font-size: 9.5px;
    color: #64748b;
    line-height: 1.35;
  }}

  /* Two Column Layout on Page 2 */
  .grid-2 {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 12px;
  }}

  .img-card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 7px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }}

  .img-card-header {{
    padding: 6px 10px;
    background: #ffffff;
    border-bottom: 1px solid #e2e8f0;
    font-size: 10.5px;
    font-weight: 700;
    color: #1e293b;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}

  .img-card-body {{
    padding: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 1;
    background: #ffffff;
  }}

  .img-card-body img {{
    max-width: 100%;
    max-height: 170px;
    object-fit: contain;
    border-radius: 4px;
  }}

  /* Big Full Report Container */
  .full-report-card {{
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
  }}

  .full-report-header {{
    padding: 7px 12px;
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 11px;
    font-weight: 700;
    color: #0f172a;
  }}

  .full-report-body {{
    padding: 4px;
    background: #ffffff;
  }}

  .full-report-body img {{
    width: 100%;
    max-height: 235px;
    object-fit: cover;
    object-position: top;
    display: block;
    border-radius: 4px;
  }}

  /* Footer */
  .footer {{
    border-top: 1px solid #f1f5f9;
    padding-top: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 9.5px;
    color: #94a3b8;
    font-weight: 500;
  }}

  .footer-links {{
    color: #673ab7;
    font-weight: 600;
    text-decoration: none;
  }}
</style>
</head>
<body>

  <!-- ==================== PAGE 1 ==================== -->
  <div class="page">
    <div>
      <div class="header">
        <div class="header-left">
          <h1>🎓 Faculty Guide Selection System</h1>
          <p>Hackathon Project Brief • II MBA • Department of Management Studies</p>
        </div>
        <a href="https://faculty-selection-bitsathy.vercel.app" target="_blank" class="live-badge" title="Open live production portal">
          <span class="live-dot"></span>
          faculty-selection-bitsathy.vercel.app ↗
        </a>
      </div>

      <!-- Overview Box -->
      <div class="summary-box">
        <b>Project Vision:</b> A high-speed, fair, and tamper-proof web portal for MBA students to select their project guides on a strict <b>First-Come, First-Served (FCFS)</b> basis. Eliminates manual spreadsheet collisions, double-booking, and seat disputes with automated real-time tracking.
      </div>

      <!-- Core Stack -->
      <div class="section-title">⚡ The Technology Stack (Simple & Reliable)</div>
      <div class="grid-4">
        <div class="stack-card">
          <div class="icon">🌐</div>
          <h3>Modern Web App</h3>
          <p>Ultra-light Single Page App hosted on Vercel Edge. Sub-300ms response time on 4G/5G mobile.</p>
        </div>
        <div class="stack-card">
          <div class="icon">🔒</div>
          <h3>Google OAuth</h3>
          <p>1-tap login restricted to college accounts (<b>@bitsathy.ac.in</b>). Zero fake logins or spoofing.</p>
        </div>
        <div class="stack-card">
          <div class="icon">🐘</div>
          <h3>Supabase Backend</h3>
          <p>Cloud PostgreSQL database with row locks. Guarantees seats never overfill during traffic rush.</p>
        </div>
        <div class="stack-card">
          <div class="icon">📊</div>
          <h3>Google Sheets Sync</h3>
          <p>Automatic live sync so faculty coordinators view selections in their spreadsheet.</p>
        </div>
      </div>

      <!-- Codebase Composition Table -->
      <div class="section-title">💻 Codebase Architecture & Active Lines of Code</div>
      <div class="table-wrap">
        <table class="code-table">
          <thead>
            <tr>
              <th>Part / Layer</th>
              <th>Technology</th>
              <th style="text-align: right;">Lines of Code</th>
              <th style="text-align: right;">Share</th>
              <th>Core Responsibility</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><b>Python App Code (Backend)</b></td>
              <td><span class="pill-py">Python 3.14</span></td>
              <td style="text-align: right; font-family: 'Consolas', monospace;">1,236</td>
              <td style="text-align: right; font-weight: 600;">54.9%</td>
              <td>FCFS row-level lock allocation, Google OAuth JWT verification, Google Sheets sync</td>
            </tr>
            <tr>
              <td><b>Frontend Interface (Web App)</b></td>
              <td><span class="pill-fe">Vanilla JS + CSS</span></td>
              <td style="text-align: right; font-family: 'Consolas', monospace;">1,017</td>
              <td style="text-align: right; font-weight: 600;">45.1%</td>
              <td>Zero-dependency mobile-first SPA, live capacity meters, tactile Google cards</td>
            </tr>
            <tr>
              <td><b>Total Active Codebase</b></td>
              <td><b>Full Stack Runtime</b></td>
              <td style="text-align: right; font-family: 'Consolas', monospace;"><b>2,253</b></td>
              <td style="text-align: right;"><b>100%</b></td>
              <td><b>Production application codebase deployed on Vercel</b></td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Flowchart -->
      <div class="section-title">🔄 End-to-End Workflow Flowchart</div>
      <div class="diagram-wrap">
        <img src="flowchart.svg" alt="End to End Workflow Flowchart" />
        <div class="diagram-caption">Seamless 5-step student journey: Login ➔ Real-time Guide Counter ➔ 60s Selection ➔ Atomic Lock ➔ Coordinator Sync</div>
      </div>

      <!-- Key Problems Solved -->
      <div class="section-title">🎯 Key Problems Solved</div>
      <div class="feature-list">
        <div class="feature-item">
          <h4>Zero Seat Overfilling</h4>
          <p>Database row locks guarantee that the last remaining seat goes to exactly one student.</p>
        </div>
        <div class="feature-item">
          <h4>Fair 60s Timer</h4>
          <p>Countdown clock prevents students from opening the form and squatting on guides indefinitely.</p>
        </div>
        <div class="feature-item">
          <h4>No Impersonation</h4>
          <p>Cryptographic Google token binds each submission directly to the student's verified college identity.</p>
        </div>
      </div>
    </div>

    <div class="footer">
      <span>BIT Sathy • II MBA Business Analytics Project</span>
      <a href="https://faculty-selection-bitsathy.vercel.app" target="_blank" class="footer-links">Live Link: faculty-selection-bitsathy.vercel.app ↗</a>
      <span>Page 1 of 2</span>
    </div>
  </div>

  <!-- ==================== PAGE 2 ==================== -->
  <div class="page">
    <div>
      <div class="header">
        <div class="header-left">
          <h1>🏛️ Architecture & Live Verification</h1>
          <p>Database Structure • Student Experience • Coordinator Live Google Sheet</p>
        </div>
        <a href="https://faculty-selection-bitsathy.vercel.app" target="_blank" class="live-badge" title="Open live production portal">
          PostgreSQL + Google API ↗
        </a>
      </div>

      <!-- Database Schema SVG -->
      <div class="section-title">🗄️ Database Schema (Supabase PostgreSQL)</div>
      <div class="diagram-wrap" style="padding: 5px; background: #131316; margin-bottom: 10px;">
        <img src="supabase_schema.svg" alt="Supabase Schema Vector ERD" style="border-radius: 4px; max-height: 175px; object-fit: contain;" />
        <div class="diagram-caption" style="color: #94a3b8; margin-top: 3px;">
          Vector ERD: Relational structure enforcing student roster, attempt timers, and atomic seat reservations.
        </div>
      </div>

      <!-- Two Visual Proofs: Student Confirmation + Faculty Capacity -->
      <div class="section-title">📱 Live Portal Interfaces & Automated Audit</div>
      <div class="grid-2">
        <div class="img-card">
          <div class="img-card-header">
            <span>✅ Student Confirmation Screen</span>
            <span style="color: #10b981; font-weight: 600;">Verified</span>
          </div>
          <div class="img-card-body">
            <img src="student_confirmation.png" alt="Student Confirmation Screen" />
          </div>
        </div>

        <div class="img-card">
          <div class="img-card-header">
            <span>📊 Live Faculty Capacity Counter</span>
            <span style="color: #673ab7; font-weight: 600;">Auto-Updated</span>
          </div>
          <div class="img-card-body">
            <img src="faculty_capacity_table.png" alt="Faculty Capacity Table" />
          </div>
        </div>
      </div>

      <!-- Full Live Google Sheets Report -->
      <div class="section-title">📑 Real-Time Google Sheets Master Audit Report (Live Sync)</div>
      <div class="full-report-card">
        <div class="full-report-header">
          <span>Official Coordinator Spreadsheet Sync (from II MBA - Google Sheets.pdf)</span>
          <span style="color: #188038; font-weight: 600;">⚡ Real-Time Auto-Generated</span>
        </div>
        <div class="full-report-body">
          <img src="google_sheets_full_report.png" alt="Full Google Sheets Report" />
        </div>
      </div>
    </div>

    <div class="footer">
      <span>BIT Sathy • II MBA Business Analytics Project</span>
      <a href="https://faculty-selection-bitsathy.vercel.app" target="_blank" class="footer-links">faculty-selection-bitsathy.vercel.app ↗</a>
      <span>Page 2 of 2</span>
    </div>
  </div>

</body>
</html>
"""

with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(html_content)
print(f"Wrote HTML to {HTML_PATH}")

cmd = [
    CHROME_PATH,
    "--headless=new",
    "--disable-gpu",
    "--no-pdf-header-footer",
    f"--print-to-pdf={OUTPUT_PDF}",
    HTML_PATH
]

print("Running Chrome PDF generation...")
res = subprocess.run(cmd, capture_output=True, text=True)
print("Chrome exit code:", res.returncode)

if os.path.exists(OUTPUT_PDF):
    size = os.path.getsize(OUTPUT_PDF)
    print(f"Generated PDF: {OUTPUT_PDF} ({size} bytes)")
    shutil.copyfile(OUTPUT_PDF, DOWNLOADS_PDF)
    print(f"Copied to: {DOWNLOADS_PDF}")
