var DB_KEY = "kyc_cases";

function getCases() { return JSON.parse(localStorage.getItem(DB_KEY) || "[]"); }
function saveCases(c) { localStorage.setItem(DB_KEY, JSON.stringify(c)); }

function addCase(c) {
  var all = getCases();
  c.id = "KYC-" + Math.floor(Math.random() * 90000 + 10000);
  c.createdAt = new Date().toISOString();
  all.push(c);
  saveCases(all);
  console.log("case added", c);
  return c;
}

function getCase(id) {
  return getCases().filter(function (c) { return c.id === id; })[0];
}

function updateCase(id, patch) {
  var all = getCases();
  all.forEach(function (c) { if (c.id === id) { for (var k in patch) c[k] = patch[k]; } });
  saveCases(all);
}

function seedIfEmpty() {
  if (getCases().length) return;
  saveCases([
    { id: "KYC-10001", fullName: "Priya Natarajan", dob: "1988-04-12", nationality: "IN", residenceCountry: "GB",
      idType: "passport", idNumber: "Z1234567", idExpiry: "2029-06-30", occupation: "engineer",
      sourceOfFunds: "salary", monthlyVolume: 6500, isPEP: false, faceToFace: true,
      score: 0, rating: "Low", status: "approved", createdBy: "analyst1", createdAt: "2025-02-01T09:00:00Z" },
    { id: "KYC-10002", fullName: "Marcus Oyelaran", dob: "1975-11-02", nationality: "NG", residenceCountry: "AE",
      idType: "national_id", idNumber: "NG-77120934", idExpiry: "2027-01-15", occupation: "jewellery",
      sourceOfFunds: "business", monthlyVolume: 62000, isPEP: false, faceToFace: false,
      score: 5, rating: "Medium", status: "pending_review", createdBy: "analyst1", createdAt: "2025-02-03T11:20:00Z" },
    { id: "KYC-10003", fullName: "Elena Vasquez-Ruiz", dob: "1969-08-23", nationality: "VE", residenceCountry: "ES",
      idType: "passport", idNumber: "P9081726", idExpiry: "2026-03-09", occupation: "government_official",
      sourceOfFunds: "other", monthlyVolume: 18000, isPEP: true, faceToFace: false,
      score: 8, rating: "High", status: "escalated", createdBy: "senior1", createdAt: "2025-02-04T15:45:00Z" }
  ]);
}
