from streamlit_app import *

df = load_and_process_data()
df = df[df["Cred"] == "MD"]
# set a column named doc_count to value_counts of 'Facility Name'
df["doc_count"] = df["Facility Name"].map(df["Facility Name"].value_counts())
# select all with less than 50 doctors and more than 3
df = df[(df["doc_count"] < 50) & (df["doc_count"] > 3) & (df["num_org_mem"] < 70)]
# drop duplicated NPIs keeping the first occurrence
df = df.drop_duplicates(subset=["NPI"], keep="first")
df = df[(df["Grd_yr"] >= 2000) & (df["Grd_yr"] <= 2020)]
df["full_name_city_state"] = (
    df["Facility Name"] + ", " + df["City/Town"] + ", " + df["State"]
)
acceptable_specialties = consult_specialties = [
    "OBSTETRICS/GYNECOLOGY",
    "PSYCHIATRY",
    "CARDIOVASCULAR DISEASE (CARDIOLOGY)",
    "EMERGENCY MEDICINE",
    "FAMILY PRACTICE",
    "GASTROENTEROLOGY",
    "DERMATOLOGY",
    "NEUROLOGY",
    "OPHTHALMOLOGY",
    "NEPHROLOGY",
    "INTERNAL MEDICINE",
    "ALLERGY/IMMUNOLOGY",
    "PULMONARY DISEASE",
    "UROLOGY",
    "OTOLARYNGOLOGY",
    "INTERVENTIONAL CARDIOLOGY",
    "RHEUMATOLOGY",
    "PEDIATRIC MEDICINE",
    "INTERVENTIONAL PAIN MANAGEMENT",
    "GENERAL PRACTICE",
    "ENDOCRINOLOGY",
    "GERIATRIC MEDICINE",
    "GYNECOLOGICAL ONCOLOGY",
    "HEMATOLOGY/ONCOLOGY",
    "CARDIAC ELECTROPHYSIOLOGY",
    "SLEEP MEDICINE",
    "SPORTS MEDICINE",
    "ADDICTION MEDICINE",
    "GERIATRIC PSYCHIATRY",
    "OSTEOPATHIC MANIPULATIVE MEDICINE",
    "NEUROPSYCHIATRY",
    "CLINICAL PSYCHOLOGIST",
]
df = df[df["pri_spec"].isin(acceptable_specialties)]
df.to_csv("cleaned_md_doctors.csv", index=False)
