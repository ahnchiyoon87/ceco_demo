from backend.src.modules.operations.agent import alarm_summary


def test_all_correlated_alarms_are_counted_with_late_arrivals_and_distinct_detectors():
    def event(tag, value, ts, detector='rule', kind='alarm_correlated'):
        return {'kind':kind,'payload':{'tag':tag,'value':value,'ts':ts,
            'detector':detector,'alert_type':'THRESHOLD_USL','severity':'CRITICAL'}}
    detail={'events':[event('IT-102',10,30,kind='alarm_received'),
        event('IT-102',12,40),event('IT-102',11,20),event('VT-101',8,35),
        event('VT-101',9,36,'cep'),{'kind':'action_result','payload':{'status':'stop_verified'}}]}
    result=alarm_summary(detail)
    assert result['original_count']==5
    assert len(result['groups'])==3
    current=next(g for g in result['groups'] if g['tag']=='IT-102')
    assert (current['count'],current['min_value'],current['max_value'])==(3,10,12)
    assert (current['first_ts'],current['last_ts'])==(20,40)


def test_no_alarm_events_does_not_invent_an_observation():
    result=alarm_summary({'events':[]})
    assert result['groups']==[] and result['original_count']==0
