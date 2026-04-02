import optimizer

def print_result(label, r):
    print(f"[{label}] Score={r['score']} | Temp={r['temp']}°C | Dial={r['dial']} | Steep={r['steep_sec']}s | EY={r['ey']:.2f}% | Body(PS)={r['compounds']['PS']:.4f} | Bitter(CGA/CA/MEL)={r['compounds']['CGA']:.4f}/{r['compounds']['CA']:.4f}/{r['compounds']['MEL']:.4f} | AC={r['compounds']['AC']:.4f} | SW={r['compounds']['SW']:.4f} | Dose={r['dose']}g")

print("=== Light Roast XL Optimizer ===")
results = optimizer.optimize("light", "xl", top_n=3)
for i, r in enumerate(results):
    print_result(f"Top {i+1}", r)

print("\n=== Anchor Points ===")
anchor_results = optimizer.optimize("light", "xl", temp_range=(98, 99), fixed_steep=120, fixed_dose=18.0, top_n=10)
for r in anchor_results:
    if r['dial'] == 4.3:
        print_result("Anchor XL (98-99C, dial=4.3, steep=120, dose=18)", r)
        break
else:
    if anchor_results:
        print_result("Best Anchor XL (98-99C, steep=120, dose=18)", anchor_results[0])

anchor_std = optimizer.optimize("light", "standard", temp_range=(98, 99), fixed_steep=120, fixed_dose=11.0, top_n=10)
for r in anchor_std:
    if r['dial'] == 4.3:
        print_result("Anchor STD (98-99C, dial=4.3, steep=120, dose=11)", r)
        break
else:
    if anchor_std:
        print_result("Best Anchor STD (98-99C, steep=120, dose=11)", anchor_std[0])

