"""Versioned meeting categories; cloud dictionaries are derived, never the source of truth."""
import copy
import uuid

TABLES = {'en': 'terms_zh_to_en', 'zh': 'terms_en_to_zh'}
DEFAULT_CATEGORIES = [('uncategorized', '未分类'), ('people', '人物姓名'), ('organizations', '公司机构'),
                      ('products', '产品项目'), ('technical', '专业术语')]


def normalize_catalog(current, update):
    data = copy.deepcopy(current)
    categories = copy.deepcopy(update.get('categories', data.get('categories')))
    if categories is None:
        categories = [dict(id=key, name=name, enabled=True) for key, name in DEFAULT_CATEGORIES]
    if not isinstance(categories, list) or len(categories) > 100:
        raise ValueError('分类必须是列表，最多 100 个。')
    category_ids, names = set(), set()
    for category in categories:
        if not isinstance(category, dict):
            raise ValueError('分类格式无效。')
        cid, name = str(category.get('id', '')), str(category.get('name', '')).strip()
        if not cid or len(cid) > 80 or not name or len(name) > 80 or cid in category_ids or name in names:
            raise ValueError('分类名称和 ID 不能为空或重复，最多 80 字。')
        if not isinstance(category.get('enabled', True), bool):
            raise ValueError('分类启用状态必须为布尔值。')
        category.update(id=cid, name=name, enabled=category.get('enabled', True))
        category_ids.add(cid); names.add(name)
    if 'uncategorized' not in category_ids:
        if '未分类' in names:
            raise ValueError('“未分类”是系统保留分类，请保留其原始 ID。')
        categories.insert(0, dict(id='uncategorized', name='未分类', enabled=True))
        category_ids.add('uncategorized')
        if len(categories) > 100:
            raise ValueError('包含系统“未分类”在内，最多 100 个分类。')

    entries = copy.deepcopy(data.get('entries', []))
    catalog_edited = 'entries' in update and update['entries'] != data.get('entries', [])
    if 'entries' in update and (catalog_edited or not any(table in update and update[table] != data.get(table, {}) for table in TABLES.values())):
        entries = copy.deepcopy(update['entries'])
    else:
        # Legacy API replaces one direction, retaining IDs and annotations for unchanged terms.
        for direction, table in TABLES.items():
            if table in update or 'entries' not in data:
                mapping = update.get(table, data.get(table, {}))
                if not isinstance(mapping, dict):
                    raise ValueError('术语映射必须是对象。')
                old = {e['source']: e for e in entries if e.get('direction') == direction}
                entries = [e for e in entries if e.get('direction') != direction]
                for source, target in mapping.items():
                    entry = copy.deepcopy(old.get(source, {}))
                    migrated_id = uuid.uuid5(uuid.NAMESPACE_URL, f'harry-translate:{direction}:{source}').hex
                    entry.update(id=entry.get('id', migrated_id), direction=direction, source=source, target=target,
                                 category_id=entry.get('category_id', 'uncategorized'), enabled=entry.get('enabled', True),
                                 notes=entry.get('notes', ''))
                    entries.append(entry)
    if not isinstance(entries, list) or len(entries) > 5000:
        raise ValueError('词条必须是列表，最多 5000 条。')
    ids, sources = set(), set()
    active_categories = {c['id'] for c in categories if c['enabled']}
    maps = {table: {} for table in TABLES.values()}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('词条格式无效。')
        for field in ('id', 'source', 'target'):
            value = entry.get(field, '')
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError('每条热词必须有唯一 ID、原词与译法，且长度不超过 256 字。')
            entry[field] = value.strip()
        direction = entry.get('direction')
        if not isinstance(direction, str):
            raise ValueError('词条方向必须是 en 或 zh。')
        identity = (direction, entry['source'])
        if direction not in TABLES or entry['id'] in ids or identity in sources:
            raise ValueError('同一方向的原词或词条 ID 重复；请明确选择唯一译法。')
        ids.add(entry['id']); sources.add(identity)
        if not isinstance(entry.get('enabled', True), bool):
            raise ValueError('词条启用状态必须为布尔值。')
        entry['enabled'] = entry.get('enabled', True)
        entry['category_id'] = entry.get('category_id', 'uncategorized')
        if not isinstance(entry['category_id'], str):
            raise ValueError('词条分类 ID 必须是文本。')
        if entry['category_id'] not in category_ids:
            entry['category_id'] = 'uncategorized'
        notes = entry.get('notes', '')
        if not isinstance(notes, str) or len(notes) > 1000:
            raise ValueError('备注最多 1000 字。')
        entry['notes'] = notes
        if entry['enabled'] and entry['category_id'] in active_categories:
            maps[TABLES[direction]][entry['source']] = entry['target']
    data.update(categories=categories, entries=entries, **maps)
    data['_version'] = '2.0'
    if 'description' in update:
        data['description'] = str(update['description'])[:1000]
    if 'asr_fixes' in update:
        fixes = update['asr_fixes']
        if not isinstance(fixes, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in fixes.items()):
            raise ValueError('语音纠错词库必须是文本映射。')
        data['asr_fixes'] = copy.deepcopy(fixes)
    return data
