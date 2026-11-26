fn double(n: u16) -> u16 {
    n.wrapping_add(n)
}

pub fn sample(_input: u16, _state: u16) -> u16 {
    double(7u16)
}
