from collections import OrderedDict
from itertools import (combinations,
                       product)
from reprlib import recursive_repr
from typing import (Dict,
                    Iterable,
                    Optional,
                    Sequence,
                    Set,
                    Tuple)

from dendroid import red_black
from prioq.base import PriorityQueue
from reprit.base import generate_repr

from .angular import Orientation
from .linear import (Segment,
                     find_intersections,
                     point_orientation_with_segment)
from .point import Point


class Event:
    __slots__ = ('is_left', 'start', 'complement', 'segments_ids')

    def __init__(self, is_left: bool, start: Point,
                 complement: Optional['Event'],
                 segments_ids: Sequence[int]) -> None:
        self.is_left = is_left
        self.start = start
        self.complement = complement
        self.segments_ids = segments_ids

    __repr__ = recursive_repr()(generate_repr(__init__))

    @property
    def is_vertical(self) -> bool:
        start_x, _ = self.start
        end_x, _ = self.end
        return start_x == end_x

    @property
    def end(self) -> Point:
        return self.complement.start

    @property
    def segment(self) -> Segment:
        return Segment(self.start, self.end)

    def is_above(self, point: Point) -> bool:
        return (point_orientation_with_segment(point, self.segment)
                is Orientation.CLOCKWISE)

    def is_below(self, point: Point) -> bool:
        return (point_orientation_with_segment(point, self.segment)
                is Orientation.COUNTERCLOCKWISE)


SweepLine = red_black.Tree[Event]
EventsQueue = PriorityQueue[Event]


class EventsQueueKey:
    __slots__ = ('event',)

    def __init__(self, event: Event) -> None:
        self.event = event

    __repr__ = generate_repr(__init__)

    def __eq__(self, other: 'EventsQueueKey') -> bool:
        return (self.event == other.event
                if isinstance(other, EventsQueueKey)
                else NotImplemented)

    def __lt__(self, other: 'EventsQueueKey') -> bool:
        if not isinstance(other, EventsQueueKey):
            return NotImplemented
        event, other_event = self.event, other.event
        event_start, other_event_start = event.start, other_event.start
        event_start_x, event_start_y = event_start
        other_event_start_x, other_event_start_y = other_event_start
        if event_start_x != other_event_start_x:
            # different x-coordinate,
            # the event with lower x-coordinate is processed first
            return event_start_x < other_event_start_x
        elif event_start_y != other_event_start_y:
            # different points, but same x-coordinate,
            # the event with lower y-coordinate is processed first
            return event_start_y < other_event_start_y
        elif event.is_left is not other_event.is_left:
            # same point, but one is a left endpoint
            # and the other a right endpoint,
            # the right endpoint is processed first
            return not event.is_left
        # same point, both events are left endpoints
        # or both are right endpoints
        elif event.end == other_event.end:
            return event.segments_ids < other_event.segments_ids
        else:
            return ((event if event.is_left else event.complement)
                    .is_below(other_event.end))


class SweepLineKey:
    __slots__ = ('event',)

    def __init__(self, event: Event) -> None:
        self.event = event

    __repr__ = generate_repr(__init__)

    def __eq__(self, other: 'SweepLineKey') -> bool:
        return (self.event == other.event
                if isinstance(other, SweepLineKey)
                else NotImplemented)

    def __lt__(self, other: 'SweepLineKey') -> bool:
        if not isinstance(other, SweepLineKey):
            return NotImplemented
        if self is other:
            return False
        event, other_event = self.event, other.event
        if event is other_event:
            return False
        start, other_start = event.start, other_event.start
        end, other_end = event.end, other_event.end
        orientation_with_other_start = point_orientation_with_segment(
                other_start, event.segment)
        orientation_with_other_end = point_orientation_with_segment(
                other_end, event.segment)
        if ((orientation_with_other_start is Orientation.COLLINEAR)
                and (orientation_with_other_end is Orientation.COLLINEAR)):
            # segments are collinear
            return EventsQueueKey(event) < EventsQueueKey(other_event)
        # segments are not collinear
        elif start == other_start:
            # same left endpoint, use the right endpoint to sort
            return event.is_below(other_end)
        # different left endpoint, use the left endpoint to sort
        event_start_x, event_start_y = start
        other_event_start_x, other_event_start_y = other_start
        if event_start_x == other_event_start_x:
            return event_start_y < other_event_start_y
        elif orientation_with_other_start is Orientation.COLLINEAR:
            return event.is_below(other_end)
        elif orientation_with_other_end is Orientation.COLLINEAR:
            other_orientation_with_end = point_orientation_with_segment(
                    end, other_event.segment)
            if other_orientation_with_end is Orientation.COLLINEAR:
                return event.is_below(other_start)
            else:
                return other_event.is_above(start)
        elif EventsQueueKey(event) < EventsQueueKey(other_event):
            # the line segment associated to `other_event` has been inserted
            # into sweep line after the line segment associated to `self`
            return event.is_below(other_start)
        else:
            # has the line segment associated to `self` been inserted
            # into sweep line after the line segment associated to `other`?
            other_orientation_with_start = point_orientation_with_segment(
                    start, other_event.segment)
            if other_orientation_with_start is Orientation.COLLINEAR:
                return other_event.is_above(end)
            else:
                return other_event.is_above(start)


def _to_events_queue(segments: Sequence[Segment]) -> PriorityQueue[Event]:
    segments_with_ids = sorted(
            (sorted(segment), segment_id)
            for segment_id, segment in enumerate(segments))
    events_queue = PriorityQueue(key=EventsQueueKey)
    index = 0
    while index < len(segments_with_ids):
        segment, segment_id = segments_with_ids[index]
        index += 1
        same_segments_ids = [segment_id]
        while (index < len(segments_with_ids)
               and segments_with_ids[index][0] == segment):
            same_segments_ids.append(segments_with_ids[index][1])
            index += 1
        start, end = segment
        start_event = Event(True, start, None, same_segments_ids)
        end_event = Event(False, end, start_event, same_segments_ids)
        start_event.complement = end_event
        events_queue.push(start_event)
        events_queue.push(end_event)
    return events_queue


def segments_intersect(segments: Sequence[Segment]) -> bool:
    return any(_sweep(segments))


def edges_intersect(edges: Sequence[Segment]) -> bool:
    last_edge_index = len(edges) - 1
    return any(next_segment_id - segment_id > 1
               and (segment_id != 0 or next_segment_id != last_edge_index)
               for segment_id, next_segment_id in _sweep(edges))


def segments_intersections(segments: Sequence[Segment]
                           ) -> Dict[Point, Set[Tuple[int, int]]]:
    result = OrderedDict()
    for segment_id, next_segment_id in _sweep(segments):
        for point in find_intersections(segments[segment_id],
                                        segments[next_segment_id]):
            result.setdefault(point, set()).add((segment_id, next_segment_id))
    return result


def _sweep(segments: Sequence[Segment]) -> Iterable[Tuple[int, int]]:
    events_queue = _to_events_queue(segments)
    sweep_line = red_black.tree(key=SweepLineKey)
    while events_queue:
        event = events_queue.pop()
        if len(event.segments_ids) > 1:
            # equal segments intersect
            yield from _to_unique_sorted_pairs(event.segments_ids,
                                               event.segments_ids)
        point, same_point_events = event.start, [event]
        while events_queue and events_queue.peek().start == point:
            same_point_events.append(events_queue.pop())
        for event, other_event in combinations(same_point_events, 2):
            for segment_id, other_segment_id in _to_unique_sorted_pairs(
                    event.segments_ids, other_event.segments_ids):
                if (point in segments[segment_id]
                        and point in segments[other_segment_id]):
                    yield (segment_id, other_segment_id)
        for event in same_point_events:
            if event.is_left:
                sweep_line.add(event)
                try:
                    next_event = sweep_line.next(event)
                except ValueError:
                    next_event = None
                try:
                    previous_event = sweep_line.prev(event)
                except ValueError:
                    previous_event = None
                if next_event is not None:
                    yield from _detect_intersection(event, next_event,
                                                    events_queue=events_queue)
                if previous_event is not None:
                    yield from _detect_intersection(previous_event, event,
                                                    events_queue=events_queue)
            else:
                event = event.complement
                if event not in sweep_line:
                    continue
                try:
                    next_event = sweep_line.next(event)
                except ValueError:
                    next_event = None
                try:
                    previous_event = sweep_line.prev(event)
                except ValueError:
                    previous_event = None
                sweep_line.remove(event)
                if next_event is not None and previous_event is not None:
                    yield from _detect_intersection(previous_event, next_event,
                                                    events_queue=events_queue)


def _detect_intersection(first_event: Event, second_event: Event,
                         events_queue: PriorityQueue
                         ) -> Iterable[Tuple[Point, Tuple[int, int]]]:
    def divide_segment(event: Event, point: Point) -> None:
        # "left event" of the "right line segment"
        # resulting from dividing event.segment
        left_event = Event(True, point, event.complement, event.segments_ids)
        # "right event" of the "left line segment"
        # resulting from dividing event.segment
        right_event = Event(False, point, event, event.segments_ids)
        event.complement.complement, event.complement = left_event, right_event
        events_queue.push(left_event)
        events_queue.push(right_event)

    intersections_points = find_intersections(first_event.segment,
                                              second_event.segment)

    if not intersections_points:
        return

    # The line segments associated to le1 and le2 intersect
    if len(intersections_points) == 1:
        point, = intersections_points
        if point != first_event.start and point != first_event.end:
            divide_segment(first_event, point)
        if point != second_event.start and point != second_event.end:
            divide_segment(second_event, point)
        yield from _to_unique_sorted_pairs(first_event.segments_ids,
                                           second_event.segments_ids)
        return

    # The line segments associated to le1 and le2 overlap
    sorted_events = []
    if first_event.start == second_event.start:
        sorted_events.append(None)
    elif EventsQueueKey(first_event) < EventsQueueKey(second_event):
        sorted_events.append(second_event)
        sorted_events.append(first_event)
    else:
        sorted_events.append(first_event)
        sorted_events.append(second_event)

    if first_event.end == second_event.end:
        sorted_events.append(None)
    elif (EventsQueueKey(first_event.complement)
          < EventsQueueKey(second_event.complement)):
        sorted_events.append(second_event.complement)
        sorted_events.append(first_event.complement)
    else:
        sorted_events.append(first_event.complement)
        sorted_events.append(second_event.complement)

    if len(sorted_events) == 2:
        # both line segments are equal
        return
    yield from _to_unique_sorted_pairs(first_event.segments_ids,
                                       second_event.segments_ids)
    if len(sorted_events) == 3:
        # line segments share endpoint
        if sorted_events[2]:
            # line segments share the left endpoint
            divide_segment(sorted_events[2].complement, sorted_events[1].start)
        else:
            # line segments share the right endpoint
            divide_segment(sorted_events[0], sorted_events[1].start)
        return
    elif sorted_events[0] is not sorted_events[3].complement:
        # no line segment includes totally the other one
        divide_segment(sorted_events[0], sorted_events[1].start)
        divide_segment(sorted_events[1], sorted_events[2].start)
    else:
        # one line segment includes the other one
        divide_segment(sorted_events[0], sorted_events[1].start)
        divide_segment(sorted_events[3].complement, sorted_events[2].start)


def _to_unique_sorted_pairs(left_iterable: Iterable[int],
                            right_iterable: Iterable[int]
                            ) -> Iterable[Tuple[int, int]]:
    for left_element, right_element in product(left_iterable, right_iterable):
        if left_element != right_element:
            yield ((left_element, right_element)
                   if left_element < right_element
                   else (right_element, left_element))