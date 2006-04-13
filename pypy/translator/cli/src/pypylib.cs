using System;

namespace pypy.runtime
{
    public class Utils
    {
        public static object RuntimeNew(Type t)
        {
            return t.GetConstructor(new Type[0]).Invoke(new object[0]);
        }
    }

    public class List<T>: System.Collections.Generic.List<T>
    {
        public int length()
        {
            return this.Count;
        }

        public T getitem_nonneg(int index)
        {
            return this[index];
        }

        public void setitem_nonneg(int index, T value_)
        {
            this[index] = value_;
        }

        public void append(T item)
        {
            this.Add(item);
        }

        public void extend(List<T> other)
        {
            this.AddRange(other);
        }

    }
}
