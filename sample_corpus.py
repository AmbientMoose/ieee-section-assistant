"""
Bundled fallback corpus so the prototype runs even with no network access.

These short passages paraphrase PUBLIC IEEE guidance (MGA tools, reporting,
Concur expense rules) gathered from ieee.org for demonstration only. When the
real PDFs are downloaded by ingest.py, they supersede this sample.
"""

SAMPLE_CHUNKS = [
    {
        "doc_id": "sample_vtools", "doc_title": "IEEE vTools Overview (sample)",
        "category": "Tools", "page": 1,
        "text": ("vTools is a suite of web applications sponsored by IEEE Member "
                 "and Geographic Activities (MGA) that simplifies volunteer and "
                 "administrative tasks for Sections, Chapters, and Student Branches. "
                 "The suite includes eNotice, Events, Officer Reporting, Voting, "
                 "Student Branch Reporting, WebInABox, and Xtreme Registration. "
                 "vTools are free to use. Access is granted automatically to any "
                 "volunteer who appears in the Geographic Units section of the IEEE "
                 "Corporate Roster."),
    },
    {
        "doc_id": "sample_reporting", "doc_title": "IEEE Officer & Meeting Reporting (sample)",
        "category": "Reporting", "page": 1,
        "text": ("Officer reporting is submitted online in vTools Officer Reporting "
                 "as part of basic reporting requirements. Current geographic-unit "
                 "volunteers can enter new officers and view, remove, or replace "
                 "existing officers. Meeting activity is reported through vTools "
                 "Events / Meeting Reporting. Keeping officer and meeting reporting "
                 "current is tied to a unit's good standing and rebate eligibility."),
    },
    {
        "doc_id": "sample_concur", "doc_title": "IEEE Concur Expense Rules (sample)",
        "category": "Concur / Expenses", "page": 1,
        "text": ("IEEE volunteers submit reimbursements through Concur (NextGen "
                 "Expense), a cloud-based expense platform. Receipts are required "
                 "for any expense item of 25.00 USD or larger. Expense reports "
                 "should be completed and submitted no later than 45 days after the "
                 "event. Reports processed in NextGen Expense are reimbursed "
                 "electronically. For air travel, only coach/economy class airfare "
                 "is reimbursable; business or first class is not reimbursable."),
    },
    {
        "doc_id": "sample_ou_analytics", "doc_title": "IEEE OU Analytics (sample)",
        "category": "OU Analytics / Membership", "page": 1,
        "text": ("OU Analytics is IEEE's dashboard-driven member-data tool, powered "
                 "by Tableau, that lets authorized officers access member data for "
                 "their organizational unit, including rosters and membership "
                 "analytics used for recruitment and retention. OU Analytics "
                 "replaced SAMIEEE, which was sunset; volunteers should use OU "
                 "Analytics in its place. Access is role-based and tied to the "
                 "officer's position in the IEEE Corporate Roster, and use of "
                 "member data is governed by IEEE privacy rules."),
    },
    {
        "doc_id": "sample_manual", "doc_title": "IEEE MGA Operations Manual (sample)",
        "category": "Governance / Operations", "page": 1,
        "text": ("The IEEE MGA Operations Manual governs Member and Geographic "
                 "Activities, including geographic-unit governance, officer roles, "
                 "and reporting requirements. It is updated periodically and sits "
                 "within the hierarchy of the IEEE Constitution, Bylaws, and "
                 "Policies. Sections operate under MGA regulations together with "
                 "their own Region and Section bylaws."),
    },


    {
        "doc_id": "sample_vtools_kb", "doc_title": "vTools Knowledge Base (sample)",
        "category": "vTools Knowledge Base", "page": 1,
        "text": ("The vTools Knowledge Base (kb.ieee.org/vtools) provides how-to "
                 "articles and tutorials for the vTools applications, including "
                 "managing Events, creating and sending eNotices from the eNotice "
                 "dashboard, officer mailings, pulling an Events report for your OU, "
                 "and using vTools Engage. Volunteers use these articles for "
                 "step-by-step guidance when operating each tool."),
    },
]
