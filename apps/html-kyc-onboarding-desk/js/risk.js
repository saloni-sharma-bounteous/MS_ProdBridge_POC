var HIGH_RISK_COUNTRIES = ["IR", "KP", "SY", "MM", "AF", "YE"];
var CASH_INTENSIVE = ["casino", "money_service", "car_dealer", "jewellery"];

function scoreCase(c) {
  var s = 0;
  if (HIGH_RISK_COUNTRIES.indexOf(c.nationality) > -1) s += 3;
  if (HIGH_RISK_COUNTRIES.indexOf(c.residenceCountry) > -1) s += 3;
  if (c.isPEP) s += 3;
  if (CASH_INTENSIVE.indexOf(c.occupation) > -1) s += 2;
  if (c.monthlyVolume > 50000) s += 2;
  else if (c.monthlyVolume > 10000) s += 1;
  if (c.sourceOfFunds === "other" || c.sourceOfFunds === "unknown") s += 2;
  if (!c.faceToFace) s += 1;
  return { score: s, rating: ratingFromScore(s) };
}

function ratingFromScore(s) {
  if (s >= 6) return "High";
  if (s >= 3) return "Medium";
  return "Low";
}

function approverFor(rating) {
  if (rating === "High") return "compliance_officer";
  if (rating === "Medium") return "senior_analyst";
  return "analyst";
}
