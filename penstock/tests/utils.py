# -*- coding: utf-8 -*-


class AlmostAlwaysTrue(object):
    def __init__(self, total_iterations=1):
        self.total_iterations = total_iterations
        self.current_iteration = 0

    def __nonzero__(self):
        if self.current_iteration < self.total_iterations:
            self.current_iteration += 1
            return bool(1)
        return bool(0)


def get_doc_by_data(db, test_data):
    founded_doc = None
    for doc_id in db:
        doc = db[doc_id]
        if doc.get('source') == test_data['source'] and doc.get('target') == test_data['target']:
            founded_doc = doc
            break
    return founded_doc
