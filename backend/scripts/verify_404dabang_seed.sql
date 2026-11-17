-- 1) Verify all seed ingredients and compare base_unit with the JSON.
SELECT id, name, base_unit
FROM inventory_ingredient
WHERE name IN (
    '원두', '디카페인원두', '우유', '귀리음료', '아몬드시럽', '바닐라시럽',
    '생크림', '초코소스', '아이스티용 티베이스', '녹차 베이스', '홍차 베이스',
    '황매실청', '복숭아·살구청', '패션후르츠청', '자몽청', '아쿠아로사 과일 베이스',
    '레몬청', '탄산수', '오렌지주스원액', '케이크시트', '크림치즈', '푸딩믹스',
    '고구마페이스트', '마스카포네 치즈', '레몬 커드', '바나나', '블루베리 퓨레'
)
ORDER BY name;

-- 2) Verify one active seed recipe per menu, including unchanged temperature.
SELECT
    m.pos_code,
    m.id AS menu_id,
    m.serving_temperature,
    r.id AS recipe_id,
    r.valid_from,
    r.valid_to,
    COUNT(ri.id) AS recipe_item_count
FROM store_menu AS m
LEFT JOIN inventory_recipe AS r
    ON r.menu_id = m.id
    AND r.variant = 'STANDARD'
    AND r.version = 1
    AND r.valid_from = '2025-01-01'
    AND r.valid_to IS NULL
    AND r.is_active = 1
LEFT JOIN inventory_recipeitem AS ri ON ri.recipe_id = r.id
WHERE m.store_id = (
    SELECT id FROM store_store WHERE name = '404다방'
)
AND m.pos_code IN (
    'M001', 'M002', 'M003', 'M004', 'M005', 'M006', 'M007', 'M008', 'M009',
    'M010', 'M011', 'M012', 'M013', 'M014', 'M015', 'M016', 'M017', 'M018',
    'M019', 'M020', 'M021', 'M022', 'M023', 'M024', 'M025', 'M026', 'M027'
)
GROUP BY m.pos_code, m.id, m.serving_temperature, r.id, r.valid_from, r.valid_to
ORDER BY m.pos_code;

-- 3) Aggregate expected counts: 27 recipes, 27 menus, 59 items, 27 used ingredients.
SELECT
    COUNT(DISTINCT r.id) AS recipe_count,
    COUNT(DISTINCT r.menu_id) AS linked_menu_count,
    COUNT(ri.id) AS recipe_item_count,
    COUNT(DISTINCT ri.ingredient_id) AS used_ingredient_count
FROM inventory_recipe AS r
JOIN store_menu AS m ON m.id = r.menu_id
LEFT JOIN inventory_recipeitem AS ri ON ri.recipe_id = r.id
WHERE m.store_id = (
    SELECT id FROM store_store WHERE name = '404다방'
)
AND m.pos_code IN (
    'M001', 'M002', 'M003', 'M004', 'M005', 'M006', 'M007', 'M008', 'M009',
    'M010', 'M011', 'M012', 'M013', 'M014', 'M015', 'M016', 'M017', 'M018',
    'M019', 'M020', 'M021', 'M022', 'M023', 'M024', 'M025', 'M026', 'M027'
)
AND r.variant = 'STANDARD'
AND r.version = 1
AND r.valid_from = '2025-01-01'
AND r.valid_to IS NULL
AND r.is_active = 1;
