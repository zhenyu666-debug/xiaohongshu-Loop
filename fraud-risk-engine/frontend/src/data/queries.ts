// Mock GSQL query code — matching the exact queries from the video

export const GSQL_QUERIES = [
  {
    id: "accountMatching",
    name: "accountMatching",
    description: "Sub-query called by main() to score a single account pair.",
    code: `CREATE QUERY accountMatching(Account s, Double threshold) FOR GRAPH FraudRisk SYNTAX V2 {
  SetAccum<STRING> @@result;
  MinAccum<double> score = 0;

  Start = {s};

  // Traverse all feature edges and collect shared accounts
  Features = SELECT t
             FROM Start:s -(HAS_IP>:e1)- IP:t1
                    -(HAS_IP>:e2)- Account:t
             ACCUM CASE WHEN e2.type == "HAS_IP" THEN score += 0.2 END;

  Features = SELECT t
             FROM Start:s -(HAS_EMAIL>:e1)- Email:t1
                    -(HAS_EMAIL>:e2)- Account:t
             ACCUM CASE WHEN e2.type == "HAS_EMAIL" THEN score += 0.3 END;

  Features = SELECT t
             FROM Start:s -(HAS_LASTNAME>:e1)- LastName:t1
                    -(HAS_LASTNAME>:e2)- Account:t
             ACCUM CASE WHEN e2.type == "HAS_LASTNAME" THEN score += 0.3 END;

  Features = SELECT t
             FROM Start:s -(HAS_PHONE>:e1)- Phone:t1
                    -(HAS_PHONE>:e2)- Account:t
             ACCUM CASE WHEN e2.type == "HAS_PHONE" THEN score += 0.2 END;

  Features = SELECT t
             FROM Start:s -(HAS_ADDRESS>:e1)- Address:t1
                    -(HAS_ADDRESS>:e2)- Account:t
             ACCUM CASE WHEN e2.type == "HAS_ADDRESS" THEN score += 0.1 END;

  // Insert SAME_OWNER edges where score >= threshold
  Matches = SELECT t
            FROM Start:s -(HAS_IP>|HAS_EMAIL>|HAS_LASTNAME>|HAS_PHONE>|HAS_ADDRESS>:e)- ANY:t
            WHERE t.type == "Account" AND score >= threshold
            POST-ACCUM INSERT INTO SAME_OWNER VALUES (s, t, score);
}`,
  },
  {
    id: "apAccountMatching",
    name: "apAccountMatching",
    description: "All-pairs entity resolution — optimized flat query (no sub-query).",
    code: `CREATE QUERY apAccountMatching(Double threshold) FOR GRAPH FraudRisk SYNTAX V2 {
  MapAccum<STRING, MinAccum<FLOAT>> @@scoreMap;
  MapAccum<STRING, FLOAT> @@weightMap;

  // Weight map — shared feature importance
  @@weightMap += ("HAS_IP"      -> 0.2);
  @@weightMap += ("HAS_EMAIL"   -> 0.3);
  @@weightMap += ("HAS_LASTNAME"-> 0.3);
  @@weightMap += ("HAS_PHONE"   -> 0.2);
  @@weightMap += ("HAS_ADDRESS" -> 0.1);
  @@weightMap += ("HAS_DEVICE"  -> 0.2);

  // Phase 1: Account -> Feature -> Account, accumulate score map
  Phase1 = SELECT t
           FROM Account:s -(HAS_IP|HAS_EMAIL|HAS_LASTNAME|HAS_PHONE|HAS_ADDRESS|HAS_DEVICE>:e)- ANY:t
           WHERE t.type == "Account" AND s != t
           ACCUM
             t.@scoreMap += (s.id -> @@weightMap.get(e.type));

  // Phase 2: Feature -> Account, propagate score back
  Phase2 = SELECT s
           FROM Account:s -(HAS_IP|HAS_EMAIL|HAS_LASTNAME|HAS_PHONE|HAS_ADDRESS|HAS_DEVICE>:e)- ANY:t
           ACCUM s.@scoreMap += t.@scoreMap;

  // Phase 3: Insert SAME_OWNER edges where score >= threshold
  Matches = SELECT s
            FROM Account:s
            POST-ACCUM
              FOREACH (v_id, score) IN s.@scoreMap DO
                WHEN score >= threshold AND v_id != s.id DO
                  INSERT INTO SAME_OWNER VALUES (s, v_id, score)
              END;
}`,
  },
  {
    id: "tgWCC",
    name: "tgWCC",
    description: "Weakly Connected Components — entity resolution helper.",
    code: `CREATE QUERY tg_wcc(
    STRING v_type = "Account",
    STRING e_type = "SAME_OWNER",
    INT    max_iter = 10,
    INT    print_limit = 100
) FOR GRAPH FraudRisk SYNTAX V2 {

  TYPEDEF TUPLE<STRING comp_id> Comp_Tuple;
  MapAccum<STRING, Comp_Tuple> @@components;

  Init = SELECT s
         FROM Start:s
         POST-ACCUM s.comp_id = s.id;

  Iter = SELECT s
         FROM Start:s -(e_type>:e)- ANY:t
         WHERE s != t
         ACCUM CASE
                   WHEN s.comp_id < t.comp_id THEN t.comp_id = s.comp_id
                   WHEN t.comp_id < s.comp_id THEN s.comp_id = t.comp_id
               END
         POST-ACCUM @@components += (s.comp_id -> Comp_Tuple(s.comp_id))
         LIMIT max_iter;

  PRINT @@components AS components, Init.size() AS vertexCount;
}`,
  },
];

export const SAMPLE_QUERY_OUTPUT = {
  results: [
    {
      account: "A001",
      sameOwnerAccounts: [
        { id: "A002", score: 0.8 },
        { id: "A006", score: 0.6 },
      ],
    },
    {
      account: "A003",
      sameOwnerAccounts: [{ id: "A004", score: 0.65 }],
    },
  ],
};
